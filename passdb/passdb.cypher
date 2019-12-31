/* Clear the database */
match (p) detach delete p;

/* Import all passes into a temporary class */
load csv with headers from "file:/passdb/passes.csv" as row
create (:Pass {analysis: row.analysis="True", classname: row.name, name: row.arg, parent: row.parent, file: row.file});

/* Split into AnalysisPass and other passes, then clean up */

match (p: Pass {analysis: true})
create (:AnalysisPass {classname: p.classname, name: p.name, parent: p.parent, file: p.file});

match (p: Pass {analysis: false, parent: "ModulePass"})
create (:ModulePass {classname: p.classname, name: p.name, file: p.file});

match (p: Pass {analysis: false, parent: "FunctionPass"})
create (:FunctionPass {classname: p.classname, name: p.name, file: p.file});

match (p: Pass {analysis: false, parent: "LoopPass"})
create (:LoopPass {classname: p.classname, name: p.name, file: p.file});

match (p: Pass {analysis: false, parent: "BasicBlockPass"})
create (:BasicBlockPass {classname: p.classname, name: p.name, file: p.file});

match (p: AnalysisPass)
match (q: Pass {name: p.name})
delete q;
match (p: ModulePass)
match (q: Pass {name: p.name})
delete q;
match (p: FunctionPass)
match (q: Pass {name: p.name})
delete q;
match (p: LoopPass)
match (q: Pass {name: p.name})
delete q;
match (p: BasicBlockPass)
match (q: Pass {name: p.name})
delete q;

/* Import all relations */

load csv with headers from "file:/passdb/requires.csv" as row
match (p {classname: row.name})
match (q {classname: row.link})
merge (p)-[:requires]->(q);

load csv with headers from "file:/passdb/transitive.csv" as row
match (p {classname: row.name})
match (q {classname: row.link})
merge (p)-[:transitive]->(q);

load csv with headers from "file:/passdb/optional.csv" as row
match (p {classname: row.name})
match (q {classname: row.link})
merge (p)-[:optional]->(q);

load csv with headers from "file:/passdb/preserves.csv" as row
match (p {classname: row.name})
match (q {classname: row.link})
merge (p)-[:preserves]->(q);
