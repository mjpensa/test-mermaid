# LLM Diagram Processor

A flexible Python tool that processes LLM research output, identifies code blocks (including non-standard formats), validates and fixes syntax errors, and renders visual diagrams.

## Features

- **Flexible Code Block Detection**: Identifies code blocks in multiple formats:
  - Standard Markdown (` ```mermaid ... ``` `)
  - HTML tags (`<code>`, `<pre>`)
  - BBCode style (`[code]...[/code]`)
  - "Gibberish" detection (identifies diagram code by special character density)

- **Automatic Language Detection**: Infers diagram type from content:
  - Mermaid (flowcharts, sequence diagrams, etc.)
  - PlantUML
  - Graphviz/DOT

- **Syntax Validation & Auto-Fix**: Detects and fixes common errors:
  - Missing diagram type declarations
  - Unbalanced brackets
  - Missing start/end tags
  - Invalid characters in node IDs

- **Visual Rendering**: Generates documents with rendered diagrams:
  - HTML output with embedded visuals
  - Markdown output with corrected code blocks

## Installation

1. Save the `llm_diagram_processor.py` file

2. (Optional) Install diagram rendering tools for image output:
   ```bash
   # For Mermaid (requires Node.js)
   npm install -g @mermaid-js/mermaid-cli
   
   # For Graphviz
   # Windows: Download from https://graphviz.org/download/
   # Linux: sudo apt-get install graphviz
   # Mac: brew install graphviz
   
   # For PlantUML (requires Java)
   # Download plantuml.jar from https://plantuml.com/download
   ```

3. Python 3.7+ required (no additional packages needed for basic functionality)

## Usage

### Command Line

```bash
# Basic usage - outputs HTML
python llm_diagram_processor.py input.txt

# Specify output file
python llm_diagram_processor.py input.txt -o output.html

# Generate Markdown output
python llm_diagram_processor.py input.txt -f md
```

### Python API

```python
from llm_diagram_processor import LLMOutputProcessor

# Read your LLM output
with open('research.txt', 'r') as f:
    input_text = f.read()

# Process it
processor = LLMOutputProcessor(output_format='html')
stats = processor.process(input_text, 'research_processed.html')

# Check statistics
print(f"Processed {stats['total_blocks']} code blocks")
print(f"Fixed {stats['fixed_blocks']} blocks with errors")
```

## Example Input

```
# AI Research Summary

Here's a flowchart showing the process:

graph TD
    A[Start] --> B{Is it working?
    B -->|Yes| C[Great!]
    B -->|No| D[Debug]
    D --> B

The system architecture uses multiple layers...

<code>
sequencediagram
    participant User
    participant System
    User->>System: Request
    System->>User: Response
</code>
```

## Example Output

The processor will:
1. Detect both code blocks (even though one is non-standard `<code>` format)
2. Identify them as Mermaid diagrams
3. Fix syntax errors:
   - Add missing closing bracket in flowchart
   - Fix "sequencediagram" to "sequenceDiagram" (proper case)
   - Add missing arrow syntax
4. Generate an HTML file with rendered diagrams

## How It Works

### 1. Code Block Detection
- Uses multiple regex patterns for standard formats
- Analyzes text for "gibberish" patterns (high density of special characters like `->`, `[]`, `{}`)
- Deduplicates overlapping matches

### 2. Language Inference
- Scans code content for keywords:
  - Mermaid: `graph`, `sequenceDiagram`, `flowchart`, etc.
  - PlantUML: `@startuml`, `actor`, `participant`
  - DOT: `digraph`, `node`, `edge`

### 3. Syntax Validation & Fixing
- **Mermaid**: Adds missing graph declarations, balances brackets, cleans node IDs
- **PlantUML**: Ensures `@startuml` and `@enduml` tags
- **DOT**: Adds graph declaration and closing braces

### 4. Rendering
- **HTML output**: Embeds Mermaid with JavaScript rendering, images as base64
- **Markdown output**: Outputs corrected code blocks
- Falls back gracefully if rendering tools unavailable

## Configuration

### Custom Detection Patterns

```python
from llm_diagram_processor import CodeBlockDetector

detector = CodeBlockDetector()

# Add custom pattern
detector.nonstandard_patterns.append(
    r'\[diagram\](.*?)\[/diagram\]'  # Custom BBCode-style tag
)
```

### Adjusting Gibberish Detection

```python
# Make it more/less sensitive
def custom_is_gibberish(line):
    special_chars = sum(1 for c in line if c in '[]{}()->=|:;*+#@')
    ratio = special_chars / len(line.strip()) if line.strip() else 0
    return ratio > 0.15  # Lower threshold = more sensitive

detector._is_gibberish_line = custom_is_gibberish
```

## Troubleshooting

**Q: Code blocks not being detected?**
- Check if they have enough special characters (arrows, brackets)
- Try wrapping in standard markdown fences: ` ```mermaid ... ``` `
- Manually add to detection patterns

**Q: Syntax fixes not working?**
- The tool makes best-effort fixes for common errors
- For complex issues, manually correct the code
- Check output statistics to see what was fixed

**Q: Diagrams not rendering?**
- HTML output will always work (uses CDN for Mermaid)
- Image rendering requires external tools (mmdc, graphviz, etc.)
- Check if tools are in your PATH

**Q: Processing very large files?**
- The tool processes everything in memory
- For huge files (>10MB), consider splitting into chunks
- Or increase Python's memory limit

## Limitations

- Requires Python 3.7+
- Image rendering requires external tools
- Very complex or exotic diagram syntax may not auto-fix correctly
- Gibberish detection may have false positives on certain text patterns

## License

MIT License - feel free to use and modify for your needs!
