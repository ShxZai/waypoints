// Checks every Learning-mode seed in web/index.html:
//  - strand indices are in range for the node's checklist
//  - option labels are unique, `correct` names an option, ids unique
//  - verify:"output" seeds: the code's printed output equals the correct label
//    (run with the Python given as argv[2], default "python")
// Also checks every LEARN_NODES id has a WAYPOINTS_LEARN entry and vice versa.
// Usage: node tests/check_learn_seeds.js [path-to-python]
const fs = require("fs"), path = require("path"), cp = require("child_process");
const html = fs.readFileSync(path.join(__dirname, "..", "web", "index.html"), "utf8");
const py = process.argv[2] || "python";

const start = html.indexOf("window.WAYPOINTS_LEARN = {");
const end = html.indexOf("</script>", start);
const window = {};
new Function("window", html.slice(start, end))(window);
const LEARN = window.WAYPOINTS_LEARN;

const learnNodes = eval(html.match(/const LEARN_NODES = (\[[^\]]*\]);/)[1]);
const checklistLen = id => {
  const m = html.match(new RegExp(String.raw`\{ id: "` + id + String.raw`",[^\n]*checklist: \[([\s\S]*?)\] \}`));
  return m ? eval("[" + m[1] + "]").length : -1;
};

let fails = 0;
const fail = msg => { fails++; console.log("FAIL " + msg); };
learnNodes.forEach(id => { if (!LEARN[id]) fail(id + " is in LEARN_NODES but has no WAYPOINTS_LEARN entry"); });
Object.keys(LEARN).forEach(id => { if (!learnNodes.includes(id)) console.log("note: " + id + " has seeds but is not in LEARN_NODES"); });

for (const [id, d] of Object.entries(LEARN)) {
  const n = checklistLen(id);
  if (!d.goal || !d.goal.question || !(d.goal.options || []).length) fail(id + " goal is missing");
  const ids = new Set(), strands = new Set();
  for (const s of d.seeds) {
    const tag = id + "/" + s.id;
    if (ids.has(s.id)) fail(tag + " duplicate id"); ids.add(s.id);
    if (!(s.strand >= 0 && s.strand < n)) fail(tag + " strand " + s.strand + " out of range (checklist has " + n + ")");
    strands.add(s.strand);
    const labels = s.options.map(o => o.label), values = s.options.map(o => o.value);
    if (new Set(labels).size !== labels.length) fail(tag + " duplicate option labels");
    if (new Set(values).size !== values.length) fail(tag + " duplicate option values");
    const correct = [].concat(s.correct);
    if (correct.length !== 1 || !values.includes(correct[0])) fail(tag + " correct must name exactly one option");
    if (!s.explanation) fail(tag + " has no explanation");
    if (s.verify === "output") {
      const r = cp.spawnSync(py, ["-I", "-c", s.code], { encoding: "utf8", timeout: 10000 });
      const out = (r.stdout || "").replace(/\r\n/g, "\n").trim();
      const want = s.options.find(o => o.value === correct[0]).label;
      if (out !== want) fail(tag + " prints " + JSON.stringify(out) + " but the key says " + JSON.stringify(want) + (r.stderr ? "\n" + r.stderr : ""));
      labels.filter(l => l !== want).forEach(l => { if (l === out) fail(tag + " a distractor equals the output"); });
    }
  }
  if (strands.size !== n) console.log("note: " + id + " seeds cover " + strands.size + " of " + n + " strands");
  console.log(id + ": " + d.seeds.length + " seeds checked");
}
console.log(fails ? fails + " problem(s)" : "All seeds OK");
process.exit(fails ? 1 : 0);
