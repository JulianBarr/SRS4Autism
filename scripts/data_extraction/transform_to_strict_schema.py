import rdflib
from rdflib import Graph, URIRef, Literal
from rdflib.namespace import RDF, RDFS
import time

def main():
    start_time = time.time()
    
    # Define namespaces
    HHH_KG = rdflib.Namespace("http://cuma.org/schema/hhh/")
    HHH_INST = rdflib.Namespace("http://cuma.org/instance/hhh/")

    # Setup graph
    g = Graph()
    g.bind("hhh-kg", HHH_KG)
    g.bind("hhh-inst", HHH_INST)
    g.bind("rdfs", RDFS)

    input_file = "scripts/data_extraction/21_heep_hong_language_abox_cleaned.ttl"
    output_file = "scripts/data_extraction/21_heep_hong_language_strict_abox.ttl"

    print(f"Loading {input_file}...")
    g.parse(input_file, format="turtle")
    initial_len = len(g)
    print(f"Loaded graph with {initial_len} triples.")

    # Step 1: Prune the Noise
    NOISE_KEYWORDS = ["序言", "引言", "出版资讯", "制作团队", "参考书目"]

    def is_noise(node):
        level = g.value(node, HHH_KG.originalLevel)
        level_val = str(level) if level else None
        if level_val == "L2":
            label = g.value(node, RDFS.label)
            if label:
                label_str = str(label)
                for kw in NOISE_KEYWORDS:
                    if kw in label_str:
                        return True
        return False

    # Find root noise nodes
    noise_roots = set()
    for s in g.subjects(HHH_KG.originalLevel, Literal("L2")):
        if is_noise(s):
            noise_roots.add(s)

    # Function to get all descendants recursively
    def get_descendants(node, descendants_set):
        for o in g.objects(node, HHH_KG.hasSubConcept):
            if isinstance(o, URIRef) and o not in descendants_set:
                descendants_set.add(o)
                get_descendants(o, descendants_set)
        for o in g.objects(node, HHH_KG.targetsConcept):
            if isinstance(o, URIRef) and o not in descendants_set:
                descendants_set.add(o)
                get_descendants(o, descendants_set)

    # Collect all nodes to delete
    nodes_to_delete = set(noise_roots)
    for root in noise_roots:
        get_descendants(root, nodes_to_delete)

    print(f"Found {len(nodes_to_delete)} noise nodes to delete.")

    # Delete the nodes and any triples they are part of
    for node in nodes_to_delete:
        for s, p, o in list(g.triples((node, None, None))):
            g.remove((s, p, o))
        for s, p, o in list(g.triples((None, None, node))):
            g.remove((s, p, o))

    print(f"Graph size after pruning: {len(g)} triples.")

    # Step 2: Mutate to align with Blueprint
    LEVEL_MAP = {
        "L1": (HHH_KG.Module, HHH_KG.hasSubmodule),
        "L2": (HHH_KG.Submodule, HHH_KG.hasLearningFocus),
        "L3": (HHH_KG.LearningFocus, HHH_KG.hasCurriculumItem),
        "L4": (HHH_KG.CurriculumItem, HHH_KG.hasTarget),
        "L5": (HHH_KG.TargetObjective, HHH_KG.hasActivity),
        "L6": (HHH_KG.ActivitySuggestion, HHH_KG.requiresMaterial),
        "L7": (HHH_KG.Material, None)
    }

    subjects_with_level = list(g.subjects(HHH_KG.originalLevel, None))
    mutated_nodes = 0

    for s in subjects_with_level:
        # Re-check if node exists, since we deleted some nodes
        if (s, None, None) not in g:
            continue
            
        level = str(g.value(s, HHH_KG.originalLevel))
        if level not in LEVEL_MAP:
            continue
        
        new_type, new_downward_edge = LEVEL_MAP[level]
        
        # Change rdf:type
        for o in list(g.objects(s, RDF.type)):
            g.remove((s, RDF.type, o))
        g.add((s, RDF.type, new_type))
        
        # Change downward edges
        for p in [HHH_KG.hasSubConcept, HHH_KG.targetsConcept]:
            for o in list(g.objects(s, p)):
                g.remove((s, p, o))
                if new_downward_edge is not None:
                    g.add((s, new_downward_edge, o))
                    
        mutated_nodes += 1

    print(f"Mutated {mutated_nodes} nodes to strict schema.")

    # Step 3: Export
    print(f"Saving to {output_file}...")
    g.serialize(destination=output_file, format="turtle")
    
    elapsed = time.time() - start_time
    print(f"Done in {elapsed:.3f} seconds.")

if __name__ == "__main__":
    main()
