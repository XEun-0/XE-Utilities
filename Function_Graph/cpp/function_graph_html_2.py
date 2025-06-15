import os
import re
from collections import defaultdict
from json import dumps

FUNC_DEF_PATTERN = re.compile(r'^\s*(?:[\w:<>&\*]+\s+)+((?:\w+::)?\w+)\s*\(([^)]*)\)\s*(\{)?\s*$')
FUNC_CALL_PATTERN = re.compile(r'(?<![\w:])(\w+)\s*\(')

RESERVED_KEYWORDS = {
    'if', 'for', 'while', 'switch', 'return', 'sizeof', 'catch', 'else',
    'delete', 'new', 'case', 'break', 'continue', 'static_cast',
    'dynamic_cast', 'reinterpret_cast', 'const_cast'
}

function_defs = {}
function_calls = defaultdict(set)
call_counts = defaultdict(int)
called_by = defaultdict(set)

def find_source_files(root='.'): 
    exts = ('.cpp', '.cc', '.c')
    source_files = []
    for dirpath, _, filenames in os.walk(root):
        for file in filenames:
            if file.endswith(exts):
                source_files.append(os.path.join(dirpath, file))
    return source_files

def extract_functions_and_calls(filepath):
    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()

    current_func = None
    brace_depth = 0
    pending_func_name = None

    for i, line in enumerate(lines):
        stripped = line.strip()

        match = FUNC_DEF_PATTERN.match(line)
        if match:
            func_name = match.group(1)
            has_brace = match.group(3)

            if has_brace:
                current_func = func_name
                brace_depth = 1
                function_defs[func_name] = (filepath, i + 1)
            else:
                pending_func_name = func_name
                continue

        elif pending_func_name and '{' in stripped:
            current_func = pending_func_name
            brace_depth = 1
            function_defs[pending_func_name] = (filepath, i + 1)
            pending_func_name = None

        elif pending_func_name and not stripped:
            continue
        elif pending_func_name:
            pending_func_name = None

        if current_func:
            brace_depth += line.count("{") - line.count("}")
            if brace_depth <= 0:
                current_func = None
                continue

            for call in FUNC_CALL_PATTERN.findall(line):
                if call in RESERVED_KEYWORDS or not call.isidentifier():
                    continue
                function_calls[current_func].add(call)
                call_counts[call] += 1
                called_by[call].add(current_func)

def generate_html(output_file="function_graph.html"):
    nodes = []
    links = []
    id_map = {}
    id_counter = 0
    connection_counts = defaultdict(int)

    for caller, callees in function_calls.items():
        connection_counts[caller] += len(callees)
        for callee in callees:
            connection_counts[callee] += 1

    for func in function_defs:
        egress = len(function_calls.get(func, []))
        ingress = len(called_by.get(func, []))

        if ingress == 0 and egress > 0:
            color = "#1f77b4"
        elif egress == 0 and ingress > 0:
            color = "#2ca02c"
        elif ingress > egress:
            color = "#d62728"
        elif egress > ingress:
            color = "#ff7f0e"
        else:
            color = "#9467bd"

        id_map[func] = id_counter
        size = 8 + 2 * connection_counts[func]
        nodes.append({'id': id_counter, 'name': func, 'size': size, 'color': color})
        id_counter += 1

    for caller, callees in function_calls.items():
        if caller in id_map:
            for callee in callees:
                if callee in id_map:
                    links.append({'source': id_map[caller], 'target': id_map[callee]})

    with open(output_file, 'w') as f:
        f.write(updated_generate_html(nodes, links))
    print(f"\n✅ HTML graph written to: {output_file}")

def updated_generate_html(nodes, links):
    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>Function Call Graph</title>
<script src="https://d3js.org/d3.v7.min.js"></script>
<style>
    body {{ margin: 0; overflow: hidden; background: #f5f5f5; }}
    text {{ font: 12px sans-serif; fill: black; stroke: white; stroke-width: 3px; paint-order: stroke; pointer-events: none; }}
    .arrow {{ fill: #aaa; }}
    .legend {{ font: 12px sans-serif; }}
</style>
</head>
<body>
<script>
    const nodes = {dumps(nodes)};
    const links = {dumps(links)};
    const width = window.innerWidth;
    const height = window.innerHeight;

    const svg = d3.select("body")
        .append("svg")
        .attr("width", width)
        .attr("height", height)
        .call(d3.zoom().on("zoom", event => {{ container.attr("transform", event.transform); }}));

    svg.append("defs").append("marker")
        .attr("id", "arrow")
        .attr("viewBox", "0 -5 10 10")
        .attr("refX", 10).attr("refY", 0)
        .attr("markerWidth", 6).attr("markerHeight", 6).attr("orient", "auto")
        .append("path").attr("d", "M0,-5L10,0L0,5").attr("class", "arrow");

    const container = svg.append("g");

    const simulation = d3.forceSimulation(nodes)
        .force("link", d3.forceLink(links).id(d => d.id).distance(100))
        .force("charge", d3.forceManyBody().strength(-300))
        .force("center", d3.forceCenter(width / 2, height / 2))
        .force("collision", d3.forceCollide().radius(d => d.size + 4));

    container.append("g").attr("stroke", "#aaa").attr("stroke-width", 1.5)
        .selectAll("line").data(links).join("line")
        .attr("marker-end", "url(#arrow)");

    const node = container.append("g")
        .selectAll("g").data(nodes).join("g")
        .call(d3.drag()
            .on("start", (event, d) => {{ if (!event.active) simulation.alphaTarget(0.3).restart(); d.fx = d.x; d.fy = d.y; }})
            .on("drag", (event, d) => {{ d.fx = event.x; d.fy = event.y; }})
            .on("end", (event, d) => {{ if (!event.active) simulation.alphaTarget(0); d.fx = null; d.fy = null; }}));

    node.append("circle")
        .attr("r", d => d.size)
        .attr("fill", d => d.color);

    node.append("text")
        .text(d => d.name)
        .attr("x", d => d.size + 4)
        .attr("y", 4);

    simulation.on("tick", () => {{
        container.selectAll("line")
            .attr("x1", d => d.source.x)
            .attr("y1", d => d.source.y)
            .attr("x2", d => d.target.x)
            .attr("y2", d => d.target.y);

        node.attr("transform", d => `translate(${{d.x}},${{d.y}})`);
    }});

    svg.append("g").attr("class", "legend").attr("transform", "translate(10,10)")
        .selectAll("g")
        .data([
            {{color: "#1f77b4", label: "Entry Point"}},
            {{color: "#2ca02c", label: "Leaf Function"}},
            {{color: "#d62728", label: "Heavily Called"}},
            {{color: "#ff7f0e", label: "Heavy Caller"}},
            {{color: "#9467bd", label: "Balanced"}},
        ])
        .join("g")
        .attr("transform", (d, i) => `translate(0,${{i * 20}})`)
        .each(function(d) {{
            d3.select(this).append("rect")
                .attr("width", 16).attr("height", 16).attr("fill", d.color);
            d3.select(this).append("text")
                .attr("x", 20).attr("y", 12).text(d.label);
        }});
</script>
</body>
</html>"""

def print_call_tree(func, visited=None, indent=0):
    if visited is None:
        visited = set()
    print("    " * indent + func)
    visited.add(func)
    for callee in sorted(function_calls.get(func, [])):
        if callee not in visited and callee in function_defs:
            print_call_tree(callee, visited, indent + 1)

def main():
    source_files = find_source_files()
    if not source_files:
        print("❌ No .cpp, .cc, or .c files found in the current directory.")
        return

    print(f"📁 Found {len(source_files)} source files. Parsing...\n")

    for filepath in source_files:
        extract_functions_and_calls(filepath)

    print("\n🔍 FUNCTION CALL TREES:\n")
    root_funcs = [f for f in function_defs if all(f not in callees for callees in function_calls.values())]

    for root in sorted(root_funcs):
        file, line = function_defs[root]
        print(f"\n📂 From: {file}:{line}")
        print_call_tree(root)

    print("\n📊 FUNCTION USAGE SUMMARY:\n")
    for func in sorted(function_defs):
        file, line = function_defs[func]
        print(f"{func}  (defined at {file}:{line})")
        print(f"  ↳ Called {call_counts[func]} time(s) by {len(called_by[func])} function(s)\n")

    generate_html()

if __name__ == "__main__":
    main()
