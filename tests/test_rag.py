import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

from river_networks.rag.agent import answer_river_query, _detect_river_mentions
from river_networks.rag.tools import list_available_rivers, get_topological_metrics
from river_networks.rag.vectorstore import retrieve_context_chunks

class TestRAGSystem(unittest.TestCase):
    def test_river_mention_detection(self):
        rivers = _detect_river_mentions("What is the diameter of Amazon and Ganges?")
        self.assertIn("amazon", rivers)
        self.assertIn("ganga", rivers)

    def test_list_available_rivers(self):
        rivers = list_available_rivers()
        ids = [r["river_id"] for r in rivers]
        self.assertIn("amazon", ids)
        self.assertIn("ganga", ids)
        self.assertIn("godavari", ids)

    def test_vectorstore_semantic_search(self):
        chunks = retrieve_context_chunks("Strahler order branching ratio", top_k=2)
        self.assertGreater(len(chunks), 0)
        self.assertTrue(any("horton" in c["source"].lower() or "graph" in c["source"].lower() for c in chunks))

    def test_riverbot_query_synthesis_and_provenance(self):
        # Query about available rivers / general question
        resp = answer_river_query("What datasets and rivers are tracked in this repository?")
        self.assertIn("HydroRIVERS", resp)
        self.assertIn("config/rivers.yaml", resp)

    @patch("river_networks.rag.agent._load_river_metrics_payload")
    def test_saved_metrics_and_missing_scaling(self, load_metrics):
        load_metrics.return_value = ({"metrics": {"diameter": {"directed": 449}}}, "network_metrics.json")
        answer = answer_river_query("What are the saved values for directed diameter and Horton ratio?",
                                   selected_basin="godavari")
        self.assertIn("449 hops", answer)
        self.assertIn("Unavailable in the saved metrics", answer)
        self.assertIn("godavari/graphs/river_graph/network_metrics.json", answer)
        self.assertNotIn("4.12", answer)

    @patch("river_networks.rag.agent._load_river_metrics_payload")
    def test_explicit_basins_override_selection(self, load_metrics):
        load_metrics.side_effect = [
            ({"edge_count": 18_703}, "network_metrics.json"),
            ({"edge_count": 16_084}, "network_metrics.json"),
        ]
        answer = answer_river_query("Compare the graph edge counts of Godavari and Krishna", selected_basin="amazon")
        self.assertIn("18,703", answer)
        self.assertIn("16,084", answer)
        self.assertEqual([call.args[0] for call in load_metrics.call_args_list], ["godavari", "krishna"])

    @patch("river_networks.rag.agent._reach_count", return_value=18_703)
    @patch("river_networks.rag.agent._load_river_metrics_payload",
           return_value=({"edge_count": 18_702}, "network_metrics.json"))
    def test_reaches_and_edges_use_distinct_sources(self, load_metrics, reach_count):
        answer = answer_river_query("How many reaches and graph edges are in Godavari?")
        self.assertIn("**Reach count:** 18,703", answer)
        self.assertIn("**Graph edge count:** 18,702", answer)
        self.assertIn("extracted_network.parquet", answer)

    def test_junction_question_counts_only_confluences_in_selected_basin(self):
        from pyarrow import table
        from pyarrow.parquet import write_table

        with TemporaryDirectory() as directory:
            graphs = Path(directory)
            (graphs / "river_graph").mkdir()
            write_table(
                table({"node_type": ["confluence/junction", "headwater", "confluence/junction",
                                    "downstream/outlet"]}),
                graphs / "river_graph" / "nodes.parquet",
            )
            with patch("river_networks.rag.agent.RiverPaths.for_river",
                       return_value=SimpleNamespace(graphs=graphs)) as paths:
                answer = answer_river_query("how many junctions are there in the network",
                                           selected_basin="ganga")
        paths.assert_called_once_with("ganga")
        self.assertIn("**Confluences / junctions:** 2", answer)
        self.assertIn("ganga/graphs/river_graph/nodes.parquet", answer)

    @patch("river_networks.rag.agent._answer_general_question")
    def test_unmapped_count_does_not_fall_back_to_documentation(self, explain):
        answer = answer_river_query("How many bridges are in this network?", selected_basin="ganga")
        self.assertEqual(answer, "This is out of scope for the bot.")
        explain.assert_not_called()

    def test_explanations_require_a_matching_topic(self):
        with patch("river_networks.rag.agent._get_api_key", return_value=None):
            supported = answer_river_query("What does directed diameter measure?")
            unsupported = answer_river_query("How is river pollution calculated?")
        self.assertIn("Longest directed downstream path", supported)
        self.assertEqual(unsupported, "This is out of scope for the bot.")

    @patch("river_networks.rag.agent._get_api_key", return_value="test-key")
    @patch("river_networks.rag.agent._call_gemini_api")
    @patch("river_networks.rag.agent._junction_count", return_value=(17, "nodes.parquet"))
    def test_model_resolves_follow_up_and_app_reads_saved_value(self, junction_count, call_model, get_key):
        call_model.return_value = '{"status":"lookup","metrics":["junction_count"],"basins":["nile"]}'
        answer = answer_river_query(
            "What about the Nile?",
            history=[
                {"role": "user", "content": "How many places do streams come together?"},
                {"role": "assistant", "content": "Previous saved result was 4231."},
            ],
            selected_basin="ganga",
        )
        junction_count.assert_called_once_with("nile")
        prompt = call_model.call_args.args[0]
        self.assertIn("How many places do streams come together?", prompt)
        self.assertNotIn("4231", prompt)
        self.assertIn("**Confluences / junctions:** 17", answer)
        self.assertIn("nile/graphs/river_graph/nodes.parquet", answer)

    @patch("river_networks.rag.agent._get_api_key", return_value="test-key")
    @patch("river_networks.rag.agent._call_gemini_api")
    @patch("river_networks.rag.agent._load_river_metrics_payload")
    def test_model_cannot_request_unapproved_data(self, loader, call_model, get_key):
        call_model.return_value = '{"status":"lookup","metrics":["../secret"],"basins":["nile"]}'
        answer = answer_river_query("How much rain fell in the Nile basin?")
        self.assertEqual(answer, "This is out of scope for the bot.")
        loader.assert_not_called()

    @patch("river_networks.rag.agent._get_api_key", return_value="test-key")
    @patch("river_networks.rag.agent._call_gemini_api", return_value='{"status":"out_of_scope"}')
    @patch("river_networks.rag.agent._reach_count")
    def test_model_can_reject_question_with_matching_keywords(self, reach_count, call_model, get_key):
        answer = answer_river_query("How many bridges cross these reaches?", selected_basin="ganga")
        self.assertEqual(answer, "This is out of scope for the bot.")
        reach_count.assert_not_called()

    @patch("river_networks.rag.agent._get_api_key", return_value="test-key")
    @patch("river_networks.rag.agent.retrieve_context_chunks", return_value=[])
    @patch("river_networks.rag.agent._call_gemini_api")
    def test_model_explains_concept_without_a_local_data_match(self, call_model, retrieve, get_key):
        call_model.return_value = "A stream capture happens when one drainage channel diverts flow from another."
        answer = answer_river_query("Why does stream capture happen?", selected_basin="ganga")
        self.assertIn("diverts flow", answer)
        self.assertNotIn("General explanation from Gemini", answer)
        self.assertNotIn("parquet", answer)
        retrieve.assert_not_called()

    @patch("river_networks.rag.agent._get_api_key", return_value="test-key")
    @patch("river_networks.rag.agent._call_gemini_api", return_value="It describes how stream counts change with stream order.")
    @patch("river_networks.rag.agent._interpret_lookup")
    @patch("river_networks.rag.agent._load_river_metrics_payload")
    def test_bare_horton_question_is_a_definition_even_with_selected_basin(
        self, load_metrics, interpret, call_model, get_key,
    ):
        for question in ("what is the horton bifurcation", "what is the horton bifurcation ratio"):
            with self.subTest(question=question):
                answer = answer_river_query(question, selected_basin="ganga", history=[
                    {"role": "user", "content": "Tell me about Strahler order"},
                    {"role": "assistant", "content": "A saved numeric result was 12345."},
                ])
                self.assertIn("stream counts change", answer)
                call = call_model.call_args
                self.assertIn("Horton bifurcation ratio", call.kwargs["system_instruction"])
                self.assertIn("Ganga", call.args[0])
                self.assertIn("Tell me about Strahler order", call.args[0])
                self.assertNotIn("12345", call.args[0])
        self.assertEqual(call_model.call_count, 2)
        interpret.assert_not_called()
        load_metrics.assert_not_called()

    @patch("river_networks.rag.agent._interpret_lookup", return_value=None)
    @patch("river_networks.rag.agent._load_river_metrics_payload")
    def test_named_basin_horton_question_uses_saved_value(self, load_metrics, interpret):
        load_metrics.return_value = ({"scaling": {"horton": {
            "bifurcation_ratio": 4.23, "r2_bifurcation": 0.997,
        }}}, "network_metrics.json")
        answer = answer_river_query("What is the Horton bifurcation ratio for Ganga?", selected_basin="nile")
        load_metrics.assert_called_once_with("ganga")
        self.assertIn("4.23", answer)
        self.assertIn("network_metrics.json", answer)
        self.assertNotIn("0.997", answer)

    @patch("river_networks.rag.agent._get_api_key", return_value="test-key")
    @patch("river_networks.rag.agent._call_gemini_api", return_value=None)
    def test_horton_definition_has_local_fallback_when_gemini_fails(self, call_model, get_key):
        answer = answer_river_query("What is the Horton bifurcation ratio?", selected_basin="ganga")
        self.assertIn("how quickly the number of streams decreases", answer)
        self.assertIn("docs/graph.md", answer)
        self.assertNotIn("network_metrics.json", answer)

    @patch("river_networks.rag.agent._answer_general_question")
    def test_unsupported_basin_strahler_request_stays_out_of_scope(self, explain):
        answer = answer_river_query("what is the strahler order for nile network", selected_basin="ganga")
        self.assertEqual(answer, "This is out of scope for the bot.")
        explain.assert_not_called()

    @patch("river_networks.rag.agent._get_api_key", return_value="test-key")
    @patch("river_networks.rag.agent._call_gemini_api", return_value=None)
    @patch("river_networks.rag.agent.retrieve_context_chunks", return_value=[])
    def test_gemini_failure_without_matching_docs_shows_out_of_scope(self, retrieve, call_model, get_key):
        answer = answer_river_query("What does this feature mean?")
        self.assertEqual(answer, "This is out of scope for the bot.")

    @patch("river_networks.rag.agent._get_api_key", return_value="test-key")
    @patch("river_networks.rag.agent._call_gemini_api")
    def test_general_answer_removes_chat_boilerplate(self, call_model, get_key):
        call_model.return_value = (
            "Hello! I am RiverBot, your research assistant for the River Networks dashboard.\n\n"
            "Strahler order ranks stream branches.\n\n"
            "- When two streams of the same order meet, the order increases by one.\n\n"
            "Regarding the Nile, I cannot provide measured numerical results or data values "
            "because the app handles basin lookups separately.\n\n"
            "General explanation from Gemini."
        )
        answer = answer_river_query("What is Strahler order?")
        self.assertEqual(
            answer,
            "Strahler order ranks stream branches.\n\n"
            "- When two streams of the same order meet, the order increases by one.",
        )
        self.assertIn("Never add greetings", call_model.call_args.kwargs["system_instruction"])

if __name__ == "__main__":
    unittest.main()
