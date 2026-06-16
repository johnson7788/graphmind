"""Language-adaptive prompt templates for GraphRAG indexing."""

from __future__ import annotations

import logging
from pathlib import Path

log = logging.getLogger("graphrag-backend")

# ── Extract graph prompt template ───────────────────────────────────────
# The prompt enforces strict language-preservation rules:
# - Entity names: MUST match the source text language exactly
# - Entity types: use the predefined type list (may be in English — OK)
# - Descriptions: written in the source text language
_EXTRACT_GRAPH_TEMPLATE = """-Goal-
Given a text document and a list of entity types, identify all entities of those types from the text and all relationships among the identified entities.

CRITICAL LANGUAGE RULES:
1. Entity names MUST be extracted EXACTLY as they appear in the source text. Do NOT translate entity names into another language.
2. If the source text is in Chinese, entity names MUST be in Chinese. For example, if the text mentions "肺", the entity name MUST be "肺", NOT "lung". If the text mentions "阿莫西林", the entity name MUST be "阿莫西林", NOT "amoxicillin".
3. Entity descriptions MUST be written in the SAME LANGUAGE as the source text.
4. Only the entity_type field uses the predefined type list (which may be in English — this is acceptable).

-Steps-
1. Identify all entities. For each identified entity, extract the following information:
- entity_name: Name of the entity, extracted EXACTLY as it appears in the source text. NEVER translate. For Chinese text, use the Chinese name. For English text, use the English name.
- entity_type: One of the following types: [{entity_types}]
- entity_description: Comprehensive description of the entity's attributes and activities, written in the SAME LANGUAGE as the source text
Format each entity as ("entity"<|><entity_name><|><entity_type><|><entity_description>)

2. From the entities identified in step 1, identify all pairs of (source_entity, target_entity) that are *clearly related* to each other.
For each pair of related entities, extract the following information:
- source_entity: name of the source entity, as identified in step 1
- target_entity: name of the target entity, as identified in step 1
- relationship_description: explanation of the relationship, in the SAME LANGUAGE as the source text
- relationship_strength: a numeric score indicating strength of the relationship
 Format each relationship as ("relationship"<|><source_entity><|><target_entity><|><relationship_description><|><relationship_strength>)

3. Return output as a single list of all entities and relationships. Use **##** as the list delimiter.

4. When finished, output <|COMPLETE|>

######################
-Examples-
######################
Example 1 (\u533b\u5b66\u6587\u6863 \u2014 Chinese input \u2192 Chinese output):
Entity_types: organ, disease, drug, symptom, medical_procedure
Text:
\u80ba\u662f\u4eba\u4f53\u91cd\u8981\u7684\u547c\u5438\u5668\u5b98\uff0c\u4f4d\u4e8e\u80f8\u8154\u5185\uff0c\u5de6\u53f3\u5404\u4e00\u3002\u80ba\u708e\u662f\u7531\u7ec6\u83cc\u3001\u75c5\u6bd2\u7b49\u75c5\u539f\u4f53\u5f15\u8d77\u7684\u80ba\u90e8\u611f\u67d3\u6027\u75be\u75c5\uff0c\u5e38\u89c1\u75c7\u72b6\u5305\u62ec\u54b3\u55fd\u3001\u53d1\u70ed\u548c\u547c\u5438\u56f0\u96be\u3002\u963f\u83ab\u897f\u6797\u662f\u4e00\u79cd\u5e38\u7528\u7684\u6297\u751f\u7d20\uff0c\u53ef\u7528\u4e8e\u6cbb\u7597\u7ec6\u83cc\u6027\u80ba\u708e\u3002\u652f\u6c14\u7ba1\u955c\u68c0\u67e5\u662f\u8bca\u65ad\u80ba\u90e8\u75be\u75c5\u7684\u91cd\u8981\u624b\u6bb5\u3002
######################
Output:
("entity"<|>\u80ba<|>organ<|>\u80ba\u662f\u4eba\u4f53\u91cd\u8981\u7684\u547c\u5438\u5668\u5b98\uff0c\u4f4d\u4e8e\u80f8\u8154\u5185\uff0c\u5de6\u53f3\u5404\u4e00\uff0c\u8d1f\u8d23\u6c14\u4f53\u4ea4\u6362)
##
("entity"<|>\u80ba\u708e<|>disease<|>\u80ba\u708e\u662f\u7531\u7ec6\u83cc\u3001\u75c5\u6bd2\u7b49\u75c5\u539f\u4f53\u5f15\u8d77\u7684\u80ba\u90e8\u611f\u67d3\u6027\u75be\u75c5)
##
("entity"<|>\u54b3\u55fd<|>symptom<|>\u54b3\u55fd\u662f\u80ba\u708e\u7684\u5e38\u89c1\u75c7\u72b6\u4e4b\u4e00)
##
("entity"<|>\u53d1\u70ed<|>symptom<|>\u53d1\u70ed\u662f\u80ba\u708e\u7684\u5e38\u89c1\u75c7\u72b6\u4e4b\u4e00)
##
("entity"<|>\u547c\u5438\u56f0\u96be<|>symptom<|>\u547c\u5438\u56f0\u96be\u662f\u80ba\u708e\u7684\u5e38\u89c1\u75c7\u72b6\u4e4b\u4e00)
##
("entity"<|>\u963f\u83ab\u897f\u6797<|>drug<|>\u963f\u83ab\u897f\u6797\u662f\u4e00\u79cd\u5e38\u7528\u7684\u6297\u751f\u7d20\uff0c\u53ef\u7528\u4e8e\u6cbb\u7597\u7ec6\u83cc\u6027\u80ba\u708e)
##
("entity"<|>\u652f\u6c14\u7ba1\u955c\u68c0\u67e5<|>medical_procedure<|>\u652f\u6c14\u7ba1\u955c\u68c0\u67e5\u662f\u8bca\u65ad\u80ba\u90e8\u75be\u75c5\u7684\u91cd\u8981\u68c0\u67e5\u624b\u6bb5)
##
("relationship"<|>\u80ba<|>\u80ba\u708e<|>\u80ba\u708e\u662f\u53d1\u751f\u5728\u80ba\u90e8\u7684\u611f\u67d3\u6027\u75be\u75c5<|>9)
##
("relationship"<|>\u80ba\u708e<|>\u54b3\u55fd<|>\u54b3\u55fd\u662f\u80ba\u708e\u7684\u5e38\u89c1\u75c7\u72b6<|>8)
##
("relationship"<|>\u80ba\u708e<|>\u53d1\u70ed<|>\u53d1\u70ed\u662f\u80ba\u708e\u7684\u5e38\u89c1\u75c7\u72b6<|>8)
##
("relationship"<|>\u80ba\u708e<|>\u547c\u5438\u56f0\u96be<|>\u547c\u5438\u56f0\u96be\u662f\u80ba\u708e\u7684\u5e38\u89c1\u75c7\u72b6<|>8)
##
("relationship"<|>\u963f\u83ab\u897f\u6797<|>\u80ba\u708e<|>\u963f\u83ab\u897f\u6797\u53ef\u7528\u4e8e\u6cbb\u7597\u7ec6\u83cc\u6027\u80ba\u708e<|>9)
##
("relationship"<|>\u652f\u6c14\u7ba1\u955c\u68c0\u67e5<|>\u80ba<|>\u652f\u6c14\u7ba1\u955c\u68c0\u67e5\u7528\u4e8e\u8bca\u65ad\u80ba\u90e8\u75be\u75c5<|>8)
<|COMPLETE|>

######################
Example 2 (\u5386\u53f2\u6587\u6863 \u2014 Chinese input \u2192 Chinese output):
Entity_types: person, location, event, organization, concept
Text:
\u96cd\u6b63\u5143\u5e74\uff0c\u4e16\u5b97\u80e4\u799b\u4e0b\u8bcf\u4ee4\u516b\u65d7\u6ee1\u6d32\u3001\u8499\u53e4\u3001\u6c49\u519b\u4eba\u5458\uff0c\u51e1\u6709\u519b\u529f\u8005\uff0c\u4ff1\u8457\u67e5\u660e\u8bae\u53d9\u3002\u9576\u9ec4\u65d7\u6ee1\u6d32\u90fd\u7edf\u5185\u5927\u81e3\u9a6c\u6b66\u594f\u79f0\uff0c\u5eb7\u7199\u516d\u5341\u4e00\u5e74\u5e73\u5b9a\u897f\u85cf\u4e4b\u5f79\uff0c\u6b63\u7ea2\u65d7\u6c49\u519b\u53c2\u9886\u674e\u536b\u529f\u52cb\u5353\u8457\uff0c\u8bf7\u6388\u4e91\u9a91\u5c09\u4e16\u804c\u3002
######################
Output:
("entity"<|>\u96cd\u6b63\u5143\u5e74<|>event<|>\u96cd\u6b63\u5143\u5e74\u662f\u6e05\u4e16\u5b97\u80e4\u799b\u5373\u4f4d\u540e\u7684\u7b2c\u4e00\u4e2a\u5e74\u53f7\u7eaa\u5e74\uff0c\u5373\u516c\u51431723\u5e74)
##
("entity"<|>\u80e4\u799b<|>person<|>\u7231\u65b0\u89c9\u7f57\u00b7\u80e4\u799b\uff0c\u5eb7\u7199\u7b2c\u56db\u5b50\uff0c\u6e05\u671d\u7b2c\u4e94\u4f4d\u7687\u5e1d\uff0c\u5e74\u53f7\u96cd\u6b63)
##
("entity"<|>\u516b\u65d7<|>organization<|>\u516b\u65d7\u5236\u5ea6\u662f\u6e05\u4ee3\u6ee1\u65cf\u7684\u519b\u4e8b\u3001\u793e\u4f1a\u7ec4\u7ec7\u5236\u5ea6\uff0c\u5206\u4e3a\u6ee1\u6d32\u516b\u65d7\u3001\u8499\u53e4\u516b\u65d7\u548c\u6c49\u519b\u516b\u65d7)
##
("entity"<|>\u9a6c\u6b66<|>person<|>\u9a6c\u6b66\u662f\u9576\u9ec4\u65d7\u6ee1\u6d32\u4eba\uff0c\u65f6\u4efb\u90fd\u7edf\u5185\u5927\u81e3)
##
("entity"<|>\u674e\u536b<|>person<|>\u674e\u536b\u662f\u6b63\u7ea2\u65d7\u6c49\u519b\u53c2\u9886\uff0c\u5728\u5eb7\u7199\u516d\u5341\u4e00\u5e74\u5e73\u5b9a\u897f\u85cf\u4e4b\u5f79\u4e2d\u7acb\u6709\u6218\u529f)
##
("entity"<|>\u4e91\u9a91\u5c09<|>concept<|>\u4e91\u9a91\u5c09\u662f\u6e05\u4ee3\u4e16\u804c\u7235\u4f4d\u4e4b\u4e00\uff0c\u4e3a\u6b63\u4e94\u54c1\u4e16\u88ad\u7235\u4f4d)
##
("entity"<|>\u897f\u85cf<|>location<|>\u897f\u85cf\u662f\u6e05\u671d\u897f\u5357\u8fb9\u7586\u5730\u533a\uff0c\u5eb7\u7199\u672b\u5e74\u66fe\u53d1\u751f\u51c6\u5676\u5c14\u5165\u4fb5\u897f\u85cf\u4e8b\u4ef6)
##
("relationship"<|>\u80e4\u799b<|>\u96cd\u6b63\u5143\u5e74<|>\u96cd\u6b63\u5143\u5e74\u7684\u5e74\u53f7\u7531\u80e4\u799b\u6240\u5b9a<|>8)
##
("relationship"<|>\u9a6c\u6b66<|>\u516b\u65d7<|>\u9a6c\u6b66\u662f\u9576\u9ec4\u65d7\u6ee1\u6d32\u90fd\u7edf<|>7)
##
("relationship"<|>\u674e\u536b<|>\u4e91\u9a91\u5c09<|>\u674e\u536b\u56e0\u6218\u529f\u88ab\u6388\u4e88\u4e91\u9a91\u5c09\u4e16\u804c<|>9)
##
("relationship"<|>\u9a6c\u6b66<|>\u674e\u536b<|>\u9a6c\u6b66\u594f\u8bf7\u4e3a\u674e\u536b\u8bae\u53d9\u519b\u529f<|>8)
<|COMPLETE|>

######################
Example 3 (English input \u2192 English output):
Entity_types: organ, disease, drug, symptom
Text:
The lungs are vital respiratory organs located in the thoracic cavity. Pneumonia is an infectious disease of the lungs caused by bacteria, viruses, and other pathogens, with common symptoms including cough, fever, and dyspnea. Amoxicillin is a commonly used antibiotic for treating bacterial pneumonia.
######################
Output:
("entity"<|>lungs<|>organ<|>The lungs are vital respiratory organs located in the thoracic cavity, responsible for gas exchange)
##
("entity"<|>Pneumonia<|>disease<|>Pneumonia is an infectious disease of the lungs caused by bacteria, viruses, and other pathogens)
##
("entity"<|>cough<|>symptom<|>Cough is one of the common symptoms of pneumonia)
##
("entity"<|>fever<|>symptom<|>Fever is one of the common symptoms of pneumonia)
##
("entity"<|>Amoxicillin<|>drug<|>Amoxicillin is a commonly used antibiotic for treating bacterial pneumonia)
##
("relationship"<|>lungs<|>Pneumonia<|>Pneumonia is an infectious disease that occurs in the lungs<|>9)
##
("relationship"<|>Pneumonia<|>cough<|>Cough is a common symptom of pneumonia<|>8)
##
("relationship"<|>Amoxicillin<|>Pneumonia<|>Amoxicillin is used to treat bacterial pneumonia<|>9)
<|COMPLETE|>

######################
-Real Data-
######################
Entity_types: {entity_types}
Text: {input_text}
######################
Output:
"""


def get_extract_graph_prompt() -> str:
    """Return the extract_graph prompt template (for testing)."""
    return _EXTRACT_GRAPH_TEMPLATE


def write_prompts(root: Path) -> None:
    """Write language-adaptive prompt templates into <root>/prompts/.

    The prompts are designed to output entity names in the SAME LANGUAGE as the
    input text. Entity types may be in English (which is acceptable), but entity
    names like "肺" must stay as "肺", not be translated to "lung".
    """
    prompts_dir = root / "prompts"
    prompts_dir.mkdir(parents=True, exist_ok=True)

    # ── extract_graph.txt ────────────────────────────────────────────────
    (prompts_dir / "extract_graph.txt").write_text(_EXTRACT_GRAPH_TEMPLATE)

    # ── summarize_descriptions.txt ───────────────────────────────────────
    (prompts_dir / "summarize_descriptions.txt").write_text("""You are a helpful assistant responsible for generating a comprehensive summary of the data provided below.
Given one or more entities, and a list of descriptions, all related to the same entity or group of entities.
Please concatenate all of these into a single, comprehensive description. Make sure to include information collected from all the descriptions.
If the provided descriptions are contradictory, please resolve the contradictions and provide a single, coherent summary.
Make sure it is written in third person, and include the entity names so we have the full context.
IMPORTANT: Write the summary in the SAME LANGUAGE as the descriptions. Do not translate.
Limit the final description length to {max_length} words.

#######
-Data-
Entities: {entity_name}
Description List: {description_list}
#######
Output:
""")

    # ── community_report_graph.txt ───────────────────────────────────────
    (prompts_dir / "community_report_graph.txt").write_text("""You are an AI assistant that helps a human analyst to perform general information discovery. Information discovery is the process of identifying and assessing relevant information associated with certain entities (e.g., organizations and individuals) within a network.

# Goal
Write a comprehensive report of a community, given a list of entities that belong to the community as well as their relationships and optional associated claims. The report will be used to inform decision-makers about information associated with the community and their potential impact.

# Report Structure
- TITLE: community's name that represents its key entities - title should be short but specific.
- SUMMARY: An executive summary of the community's overall structure.
- IMPACT SEVERITY RATING: a float score between 0-10.
- RATING EXPLANATION: a single sentence explanation.
- DETAILED FINDINGS: 5-10 key insights, each with a short summary and multiple paragraphs of explanation.

IMPORTANT: Write the report in the SAME LANGUAGE as the input data. Do not translate.

{input_text}

Output the report in JSON format:
""")

    # ── community_report_text.txt ────────────────────────────────────────
    (prompts_dir / "community_report_text.txt").write_text("""You are an AI assistant that helps a human analyst to perform general information discovery.

# Goal
Write a comprehensive report of a community, given a list of entities that belong to the community as well as their relationships and optional associated claims. Retain as much time specific information as possible.

# Report Structure
- TITLE: community's name, short but specific.
- SUMMARY: An executive summary of the community's overall structure.
- IMPORTANCE RATING: a float score between 0-10.
- RATING EXPLANATION: a single sentence explanation.
- DETAILED FINDINGS: 5-10 key insights.

IMPORTANT: Write the report in the SAME LANGUAGE as the input data. Do not translate.

{input_text}

Output the report in JSON format:
""")

    # ── Additional search prompts ────────────────────────────────────────
    (prompts_dir / "local_search_system_prompt.txt").write_text("""You are a helpful assistant that helps answer questions about the provided text context. Answer in the SAME LANGUAGE as the question. Do not translate.""")

    (prompts_dir / "global_search_map_system_prompt.txt").write_text("""You are a helpful assistant that helps map out relevant communities for a query. Answer in the SAME LANGUAGE as the question. Do not translate.""")

    (prompts_dir / "global_search_reduce_system_prompt.txt").write_text("""You are a helpful assistant that helps synthesize answers from community reports. Answer in the SAME LANGUAGE as the question. Do not translate.""")

    (prompts_dir / "global_search_knowledge_system_prompt.txt").write_text("""You are a helpful assistant that helps generate knowledge from community reports. Answer in the SAME LANGUAGE as the question. Do not translate.""")

    (prompts_dir / "drift_search_system_prompt.txt").write_text("""You are a helpful assistant that helps perform drift search queries. Answer in the SAME LANGUAGE as the question. Do not translate.""")

    (prompts_dir / "drift_search_reduce_prompt.txt").write_text("""You are a helpful assistant that helps synthesize drift search results. Answer in the SAME LANGUAGE as the question. Do not translate.""")

    (prompts_dir / "basic_search_system_prompt.txt").write_text("""You are a helpful assistant that helps answer questions using knowledge graph data. Answer in the SAME LANGUAGE as the question. Do not translate.""")

    log.info("Written language-adaptive prompts")
