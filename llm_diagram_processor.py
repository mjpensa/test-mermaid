"""
LLM Research Output Processor
Identifies code blocks (including non-standard formats), validates/fixes syntax,
and renders visuals (Mermaid, PlantUML, etc.) into a formatted output document.
"""

import re
import os
import tempfile
import subprocess
from pathlib import Path
from typing import List, Tuple, Dict, Optional
import base64


class CodeBlockDetector:
    """Detects code blocks in various formats, including non-standard ones."""
    
    def __init__(self):
        # Standard markdown code block patterns
        self.standard_patterns = [
            r'```(\w+)?\n(.*?)```',  # ```mermaid\n...\n```
            r'~~~(\w+)?\n(.*?)~~~',  # ~~~mermaid\n...\n~~~
        ]
        
        # Non-standard patterns that might appear in LLM output
        self.nonstandard_patterns = [
            r'<code[^>]*>\s*(\w+)?\s*\n(.*?)</code>',  # HTML code tags
            r'\[code(?:\s+lang="?(\w+)"?)?\](.*?)\[/code\]',  # BBCode style
            r'<pre[^>]*>\s*(\w+)?\s*\n(.*?)</pre>',  # HTML pre tags
        ]
        
    def detect_blocks(self, text: str) -> List[Dict[str, any]]:
        """
        Detects all code blocks in the text.
        Returns list of dicts with: start_pos, end_pos, language, code, original_text
        """
        blocks = []
        
        # Try standard patterns first
        for pattern in self.standard_patterns:
            for match in re.finditer(pattern, text, re.DOTALL | re.MULTILINE):
                lang = match.group(1) if match.group(1) else self._infer_language(match.group(2))
                blocks.append({
                    'start_pos': match.start(),
                    'end_pos': match.end(),
                    'language': lang,
                    'code': match.group(2).strip(),
                    'original_text': match.group(0),
                    'format': 'standard'
                })
        
        # Try non-standard patterns
        for pattern in self.nonstandard_patterns:
            for match in re.finditer(pattern, text, re.DOTALL | re.MULTILINE | re.IGNORECASE):
                lang = match.group(1) if match.group(1) else self._infer_language(match.group(2))
                blocks.append({
                    'start_pos': match.start(),
                    'end_pos': match.end(),
                    'language': lang,
                    'code': match.group(2).strip(),
                    'original_text': match.group(0),
                    'format': 'nonstandard'
                })
        
        # Look for "gibberish" blocks (high density of special chars)
        blocks.extend(self._detect_gibberish_blocks(text))
        
        # Sort by position and remove duplicates/overlaps
        blocks = self._deduplicate_blocks(blocks)
        
        return blocks
    
    def _infer_language(self, code: str) -> str:
        """Infers the diagram/code language from content."""
        code_lower = code.lower().strip()
        
        # Mermaid keywords
        if any(keyword in code_lower for keyword in ['graph', 'sequencediagram', 'classDiagram', 
                                                       'statediagram', 'erdiagram', 'gantt',
                                                       'pie', 'flowchart', 'journey']):
            return 'mermaid'
        
        # PlantUML keywords
        if any(keyword in code_lower for keyword in ['@startuml', '@enduml', 'actor', 
                                                       'participant', 'class', 'interface']):
            return 'plantuml'
        
        # Graphviz/DOT
        if any(keyword in code_lower for keyword in ['digraph', 'graph', 'subgraph', 'node', 'edge']):
            if '->' in code or '--' in code:
                return 'dot'
        
        return 'unknown'
    
    def _detect_gibberish_blocks(self, text: str) -> List[Dict[str, any]]:
        """
        Detects potential code blocks by looking for "gibberish" - 
        text with high density of special characters, arrows, brackets.
        """
        blocks = []
        lines = text.split('\n')
        current_block = []
        start_line = -1
        gibberish_count = 0
        
        for i, line in enumerate(lines):
            if self._is_gibberish_line(line):
                if not current_block:
                    start_line = i
                current_block.append(line)
                gibberish_count += 1
            else:
                if len(current_block) >= 3 and gibberish_count >= 2:
                    # Found a potential code block
                    code = '\n'.join(current_block)
                    start_pos = sum(len(lines[j]) + 1 for j in range(start_line))
                    end_pos = start_pos + len(code)
                    
                    blocks.append({
                        'start_pos': start_pos,
                        'end_pos': end_pos,
                        'language': self._infer_language(code),
                        'code': code,
                        'original_text': code,
                        'format': 'gibberish_detected'
                    })
                
                current_block = []
                gibberish_count = 0
                start_line = -1
        
        return blocks
    
    def _is_gibberish_line(self, line: str) -> bool:
        """Determines if a line looks like code/diagram syntax."""
        if not line.strip():
            return False
        
        # Count special characters commonly in diagrams
        special_chars = sum(1 for c in line if c in '[]{}()->=|:;*+#@')
        total_chars = len(line.strip())
        
        if total_chars == 0:
            return False
        
        # High ratio of special chars suggests diagram code
        ratio = special_chars / total_chars
        return ratio > 0.2
    
    def _deduplicate_blocks(self, blocks: List[Dict]) -> List[Dict]:
        """Removes duplicate and overlapping blocks."""
        if not blocks:
            return []
        
        blocks.sort(key=lambda x: (x['start_pos'], -x['end_pos']))
        result = [blocks[0]]
        
        for block in blocks[1:]:
            last = result[-1]
            # If blocks don't overlap, add it
            if block['start_pos'] >= last['end_pos']:
                result.append(block)
            # If current block is larger, replace
            elif block['end_pos'] > last['end_pos']:
                result[-1] = block
        
        return result


class SyntaxValidator:
    """Validates and fixes syntax errors in diagram code."""
    
    def validate_and_fix(self, code: str, language: str) -> Tuple[str, List[str]]:
        """
        Validates code and attempts to fix errors.
        Returns: (fixed_code, list_of_issues_found)
        """
        issues = []
        fixed_code = code
        
        if language == 'mermaid':
            fixed_code, mermaid_issues = self._fix_mermaid(code)
            issues.extend(mermaid_issues)
        elif language == 'plantuml':
            fixed_code, plantuml_issues = self._fix_plantuml(code)
            issues.extend(plantuml_issues)
        elif language == 'dot':
            fixed_code, dot_issues = self._fix_dot(code)
            issues.extend(dot_issues)
        
        return fixed_code, issues
    
    def _fix_mermaid(self, code: str) -> Tuple[str, List[str]]:
        """Fixes common Mermaid syntax errors."""
        issues = []
        lines = code.split('\n')
        fixed_lines = []
        
        for i, line in enumerate(lines):
            original_line = line
            
            # Fix: Missing semicolons (not always required but can help)
            # Fix: Unbalanced brackets
            open_brackets = line.count('[') + line.count('(') + line.count('{')
            close_brackets = line.count(']') + line.count(')') + line.count('}')
            if open_brackets != close_brackets:
                issues.append(f"Line {i+1}: Unbalanced brackets - attempting to fix")
                # Try to balance
                if open_brackets > close_brackets:
                    line = line + ']' * (open_brackets - close_brackets)
            
            # Fix: Invalid arrow syntax
            if '-->' in line and not any(valid in line for valid in ['-->', '--->', '-.->',  '==>']):
                pass  # Already valid
            
            # Fix: Missing graph type declaration
            if i == 0 and not any(keyword in line.lower() for keyword in 
                                 ['graph', 'flowchart', 'sequencediagram', 'classDiagram',
                                  'statediagram', 'erdiagram', 'gantt', 'pie', 'journey']):
                issues.append("Missing graph type declaration - adding 'graph TD'")
                fixed_lines.append('graph TD')
            
            # Fix: Invalid characters in node IDs
            if '-->' in line or '---' in line:
                # Extract node IDs and clean them
                parts = re.split(r'(-->|---|->|==>|\-\.\->)', line)
                cleaned_parts = []
                for part in parts:
                    if part in ['-->', '---', '->', '==>', '-.->']:
                        cleaned_parts.append(part)
                    else:
                        # Remove invalid chars from node content
                        cleaned = re.sub(r'[^\w\s\[\]\(\)\{\}\"\'\-\:]+', '', part)
                        cleaned_parts.append(cleaned)
                line = ''.join(cleaned_parts)
            
            fixed_lines.append(line)
        
        fixed_code = '\n'.join(fixed_lines)
        
        # Ensure proper structure
        if not any(keyword in fixed_code.lower()[:50] for keyword in 
                  ['graph', 'flowchart', 'sequencediagram', 'classDiagram']):
            issues.append("No valid diagram type found - prepending 'graph TD'")
            fixed_code = 'graph TD\n' + fixed_code
        
        return fixed_code, issues
    
    def _fix_plantuml(self, code: str) -> Tuple[str, List[str]]:
        """Fixes common PlantUML syntax errors."""
        issues = []
        
        # Ensure @startuml and @enduml tags
        if not code.strip().startswith('@startuml'):
            issues.append("Missing @startuml tag - adding")
            code = '@startuml\n' + code
        
        if not code.strip().endswith('@enduml'):
            issues.append("Missing @enduml tag - adding")
            code = code + '\n@enduml'
        
        return code, issues
    
    def _fix_dot(self, code: str) -> Tuple[str, List[str]]:
        """Fixes common DOT/Graphviz syntax errors."""
        issues = []
        
        # Ensure proper graph declaration
        if not re.match(r'^\s*(di)?graph\s+\w*\s*\{', code, re.IGNORECASE):
            issues.append("Missing graph declaration - adding 'digraph G {'")
            code = 'digraph G {\n' + code
        
        # Ensure closing brace
        if not code.strip().endswith('}'):
            issues.append("Missing closing brace - adding")
            code = code + '\n}'
        
        return code, issues


class DiagramRenderer:
    """Renders diagrams to various output formats."""
    
    def __init__(self):
        self.temp_dir = tempfile.mkdtemp()
    
    def render(self, code: str, language: str, output_format: str = 'png') -> Optional[str]:
        """
        Renders diagram code to an image or HTML.
        Returns: path to rendered file or None if failed
        """
        try:
            if language == 'mermaid':
                return self._render_mermaid(code, output_format)
            elif language == 'plantuml':
                return self._render_plantuml(code, output_format)
            elif language == 'dot':
                return self._render_dot(code, output_format)
            else:
                return None
        except Exception as e:
            print(f"Rendering failed: {e}")
            return None
    
    def _render_mermaid(self, code: str, output_format: str) -> Optional[str]:
        """Renders Mermaid diagram."""
        # For HTML output, embed Mermaid directly
        if output_format == 'html':
            return self._create_mermaid_html(code)
        
        # For image output, would need mermaid-cli (mmdc)
        # Check if mmdc is available
        try:
            input_file = os.path.join(self.temp_dir, 'diagram.mmd')
            output_file = os.path.join(self.temp_dir, f'diagram.{output_format}')
            
            with open(input_file, 'w', encoding='utf-8') as f:
                f.write(code)
            
            result = subprocess.run(['mmdc', '-i', input_file, '-o', output_file],
                                  capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0 and os.path.exists(output_file):
                return output_file
            else:
                # Fallback to HTML
                return self._create_mermaid_html(code)
        except (FileNotFoundError, subprocess.TimeoutExpired):
            # mmdc not available, use HTML fallback
            return self._create_mermaid_html(code)
    
    def _create_mermaid_html(self, code: str) -> str:
        """Creates an HTML file with embedded Mermaid diagram."""
        html_content = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <script src="https://cdn.jsdelivr.net/npm/mermaid/dist/mermaid.min.js"></script>
    <script>mermaid.initialize({{startOnLoad:true}});</script>
</head>
<body>
    <div class="mermaid">
{code}
    </div>
</body>
</html>"""
        
        output_file = os.path.join(self.temp_dir, f'mermaid_{id(code)}.html')
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        return output_file
    
    def _render_plantuml(self, code: str, output_format: str) -> Optional[str]:
        """Renders PlantUML diagram."""
        try:
            input_file = os.path.join(self.temp_dir, 'diagram.puml')
            
            with open(input_file, 'w', encoding='utf-8') as f:
                f.write(code)
            
            # Try to use plantuml.jar
            result = subprocess.run(['java', '-jar', 'plantuml.jar', input_file],
                                  capture_output=True, text=True, timeout=30)
            
            output_file = input_file.replace('.puml', '.png')
            if result.returncode == 0 and os.path.exists(output_file):
                return output_file
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
        
        return None
    
    def _render_dot(self, code: str, output_format: str) -> Optional[str]:
        """Renders DOT/Graphviz diagram."""
        try:
            input_file = os.path.join(self.temp_dir, 'diagram.dot')
            output_file = os.path.join(self.temp_dir, f'diagram.{output_format}')
            
            with open(input_file, 'w', encoding='utf-8') as f:
                f.write(code)
            
            result = subprocess.run(['dot', f'-T{output_format}', input_file, '-o', output_file],
                                  capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0 and os.path.exists(output_file):
                return output_file
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
        
        return None


class LLMOutputProcessor:
    """Main processor that orchestrates detection, validation, and rendering."""
    
    def __init__(self, output_format: str = 'html'):
        self.detector = CodeBlockDetector()
        self.validator = SyntaxValidator()
        self.renderer = DiagramRenderer()
        self.output_format = output_format
    
    def process(self, input_text: str, output_path: str) -> Dict[str, any]:
        """
        Processes LLM output and creates final document with rendered visuals.
        Returns: dict with processing statistics
        """
        print("Step 1: Detecting code blocks...")
        blocks = self.detector.detect_blocks(input_text)
        print(f"Found {len(blocks)} code blocks")
        
        stats = {
            'total_blocks': len(blocks),
            'validated_blocks': 0,
            'fixed_blocks': 0,
            'rendered_blocks': 0,
            'failed_blocks': 0,
            'issues': []
        }
        
        # Process each block
        processed_blocks = []
        for idx, block in enumerate(blocks):
            print(f"\nProcessing block {idx + 1}/{len(blocks)} ({block['language']})...")
            
            # Step 2: Validate and fix syntax
            fixed_code, issues = self.validator.validate_and_fix(block['code'], block['language'])
            stats['validated_blocks'] += 1
            
            if issues:
                stats['fixed_blocks'] += 1
                stats['issues'].extend([f"Block {idx+1}: {issue}" for issue in issues])
                print(f"  Fixed {len(issues)} issue(s)")
            
            # Step 3: Render diagram
            rendered_path = None
            if block['language'] != 'unknown':
                rendered_path = self.renderer.render(fixed_code, block['language'], self.output_format)
                
                if rendered_path:
                    stats['rendered_blocks'] += 1
                    print(f"  Rendered successfully")
                else:
                    stats['failed_blocks'] += 1
                    print(f"  Rendering failed")
            else:
                stats['failed_blocks'] += 1
                print(f"  Unknown language - skipping render")
            
            processed_blocks.append({
                'original': block,
                'fixed_code': fixed_code,
                'issues': issues,
                'rendered_path': rendered_path
            })
        
        # Step 4: Generate output document
        print("\nGenerating output document...")
        self._generate_output(input_text, processed_blocks, output_path)
        print(f"Output saved to: {output_path}")
        
        return stats
    
    def _generate_output(self, original_text: str, blocks: List[Dict], output_path: str):
        """Generates the final output document with rendered visuals."""
        
        if output_path.endswith('.html'):
            self._generate_html_output(original_text, blocks, output_path)
        elif output_path.endswith('.md'):
            self._generate_markdown_output(original_text, blocks, output_path)
        else:
            self._generate_html_output(original_text, blocks, output_path + '.html')
    
    def _generate_html_output(self, original_text: str, blocks: List[Dict], output_path: str):
        """Generates HTML output with embedded/linked visuals."""
        
        html_parts = ['<!DOCTYPE html>\n<html>\n<head>\n<meta charset="utf-8">']
        html_parts.append('<script src="https://cdn.jsdelivr.net/npm/mermaid/dist/mermaid.min.js"></script>')
        html_parts.append('<script>mermaid.initialize({startOnLoad:true});</script>')
        html_parts.append('<style>')
        html_parts.append('body { font-family: Arial, sans-serif; max-width: 1200px; margin: 0 auto; padding: 20px; }')
        html_parts.append('.diagram { margin: 20px 0; padding: 10px; border: 1px solid #ddd; background: #f9f9f9; }')
        html_parts.append('.original-code { display: none; }')
        html_parts.append('.issues { color: #d63031; font-size: 0.9em; margin: 5px 0; }')
        html_parts.append('</style>')
        html_parts.append('</head>\n<body>')
        
        # Sort blocks by position
        sorted_blocks = sorted(blocks, key=lambda x: x['original']['start_pos'])
        
        last_pos = 0
        for block_data in sorted_blocks:
            block = block_data['original']
            
            # Add text before this block
            text_before = original_text[last_pos:block['start_pos']]
            html_parts.append(self._text_to_html(text_before))
            
            # Add diagram section
            html_parts.append('<div class="diagram">')
            
            # Show issues if any
            if block_data['issues']:
                html_parts.append('<div class="issues">')
                html_parts.append(f"<strong>Fixed {len(block_data['issues'])} issue(s):</strong><br>")
                for issue in block_data['issues']:
                    html_parts.append(f"• {issue}<br>")
                html_parts.append('</div>')
            
            # Add rendered diagram
            if block_data['rendered_path']:
                if block_data['rendered_path'].endswith('.html'):
                    # Read and embed Mermaid content
                    with open(block_data['rendered_path'], 'r', encoding='utf-8') as f:
                        content = f.read()
                        # Extract just the mermaid div
                        match = re.search(r'<div class="mermaid">(.*?)</div>', content, re.DOTALL)
                        if match:
                            html_parts.append(f'<div class="mermaid">{match.group(1)}</div>')
                else:
                    # Embed image
                    with open(block_data['rendered_path'], 'rb') as f:
                        img_data = base64.b64encode(f.read()).decode()
                    html_parts.append(f'<img src="data:image/png;base64,{img_data}" alt="Diagram">')
            else:
                # Fallback: show code block
                html_parts.append(f'<pre><code>{self._escape_html(block_data["fixed_code"])}</code></pre>')
            
            html_parts.append('</div>')
            
            last_pos = block['end_pos']
        
        # Add remaining text
        html_parts.append(self._text_to_html(original_text[last_pos:]))
        
        html_parts.append('</body>\n</html>')
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(html_parts))
    
    def _generate_markdown_output(self, original_text: str, blocks: List[Dict], output_path: str):
        """Generates Markdown output with fixed code blocks."""
        
        sorted_blocks = sorted(blocks, key=lambda x: x['original']['start_pos'])
        
        result_parts = []
        last_pos = 0
        
        for block_data in sorted_blocks:
            block = block_data['original']
            
            # Add text before this block
            result_parts.append(original_text[last_pos:block['start_pos']])
            
            # Add fixed code block
            if block_data['issues']:
                result_parts.append(f"\n<!-- Fixed {len(block_data['issues'])} issue(s) -->\n")
            
            result_parts.append(f"```{block['language']}\n{block_data['fixed_code']}\n```\n")
            
            last_pos = block['end_pos']
        
        # Add remaining text
        result_parts.append(original_text[last_pos:])
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(''.join(result_parts))
    
    def _text_to_html(self, text: str) -> str:
        """Converts plain text to HTML with basic formatting."""
        # Convert markdown-style headers
        text = re.sub(r'^### (.*?)$', r'<h3>\1</h3>', text, flags=re.MULTILINE)
        text = re.sub(r'^## (.*?)$', r'<h2>\1</h2>', text, flags=re.MULTILINE)
        text = re.sub(r'^# (.*?)$', r'<h1>\1</h1>', text, flags=re.MULTILINE)
        
        # Convert newlines to <br> or <p>
        paragraphs = text.split('\n\n')
        html_paragraphs = [f'<p>{p.replace(chr(10), "<br>")}</p>' for p in paragraphs if p.strip()]
        
        return '\n'.join(html_paragraphs)
    
    def _escape_html(self, text: str) -> str:
        """Escapes HTML special characters."""
        return text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def main():
    """Example usage of the LLM Output Processor."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Process LLM research output with diagrams')
    parser.add_argument('input_file', help='Input file containing LLM research output')
    parser.add_argument('-o', '--output', help='Output file path (default: input_processed.html)',
                       default=None)
    parser.add_argument('-f', '--format', choices=['html', 'md'], default='html',
                       help='Output format (default: html)')
    
    args = parser.parse_args()
    
    # Read input file
    with open(args.input_file, 'r', encoding='utf-8') as f:
        input_text = f.read()
    
    # Determine output path
    if args.output:
        output_path = args.output
    else:
        base = os.path.splitext(args.input_file)[0]
        output_path = f"{base}_processed.{args.format}"
    
    # Process
    processor = LLMOutputProcessor(output_format=args.format)
    stats = processor.process(input_text, output_path)
    
    # Print statistics
    print("\n" + "="*60)
    print("PROCESSING COMPLETE")
    print("="*60)
    print(f"Total code blocks found: {stats['total_blocks']}")
    print(f"Validated: {stats['validated_blocks']}")
    print(f"Fixed: {stats['fixed_blocks']}")
    print(f"Rendered: {stats['rendered_blocks']}")
    print(f"Failed: {stats['failed_blocks']}")
    
    if stats['issues']:
        print("\nIssues fixed:")
        for issue in stats['issues'][:10]:  # Show first 10
            print(f"  - {issue}")
        if len(stats['issues']) > 10:
            print(f"  ... and {len(stats['issues']) - 10} more")


if __name__ == '__main__':
    main()
