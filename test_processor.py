"""
Test script for LLM Diagram Processor
Demonstrates usage and validates functionality
"""

from llm_diagram_processor import LLMOutputProcessor, CodeBlockDetector, SyntaxValidator

def test_code_detection():
    """Test code block detection with various formats."""
    print("="*60)
    print("TEST 1: Code Block Detection")
    print("="*60)
    
    test_text = """
Some regular text here.

```mermaid
graph TD
    A --> B
```

More text.

<code>
sequenceDiagram
    A->>B: Hello
</code>

[code lang="plantuml"]
@startuml
actor User
@enduml
[/code]

Random text with arrows: --> and brackets []
But this has lots of special chars: A-->B{Test}[C]|D
Should detect: graph TD; A[Start]-->B[End]
"""
    
    detector = CodeBlockDetector()
    blocks = detector.detect_blocks(test_text)
    
    print(f"\nFound {len(blocks)} code blocks:\n")
    for i, block in enumerate(blocks, 1):
        print(f"Block {i}:")
        print(f"  Language: {block['language']}")
        print(f"  Format: {block['format']}")
        print(f"  Length: {len(block['code'])} chars")
        print(f"  Preview: {block['code'][:50]}...")
        print()
    
    return len(blocks) > 0

def test_syntax_validation():
    """Test syntax validation and fixing."""
    print("="*60)
    print("TEST 2: Syntax Validation & Fixing")
    print("="*60)
    
    validator = SyntaxValidator()
    
    # Test cases with intentional errors
    test_cases = [
        ("graph TD\n    A[Start] --> B{Decision\n    B --> C", "mermaid"),
        ("@startuml\nactor User", "plantuml"),
        ("node [shape=box];\nA -> B;", "dot"),
    ]
    
    for i, (code, lang) in enumerate(test_cases, 1):
        print(f"\nTest case {i} ({lang}):")
        print("Original code:")
        print(code)
        
        fixed, issues = validator.validate_and_fix(code, lang)
        
        if issues:
            print(f"\nFound {len(issues)} issue(s):")
            for issue in issues:
                print(f"  - {issue}")
            print("\nFixed code:")
            print(fixed)
        else:
            print("\nNo issues found!")
        print("-" * 40)
    
    return True

def test_full_processing():
    """Test full processing pipeline."""
    print("="*60)
    print("TEST 3: Full Processing Pipeline")
    print("="*60)
    
    # Create sample LLM output with errors
    sample_text = """
# Test Document

Here's a flowchart:

```mermaid
graph TD
    A[Start] --> B{Check
    B --> C[End]
```

And a sequence diagram:

<code>
sequencediagram
    Alice->>Bob: Hello
    Bob->>Alice: Hi
</code>
"""
    
    print("\nInput text:")
    print(sample_text)
    print("\n" + "-"*60)
    
    # Process
    processor = LLMOutputProcessor(output_format='html')
    
    # Save sample to file
    import os
    input_file = 'test_input.txt'
    output_file = 'test_output.html'
    
    with open(input_file, 'w', encoding='utf-8') as f:
        f.write(sample_text)
    
    print("\nProcessing...")
    stats = processor.process(sample_text, output_file)
    
    print("\nProcessing Statistics:")
    print(f"  Total blocks found: {stats['total_blocks']}")
    print(f"  Validated: {stats['validated_blocks']}")
    print(f"  Fixed: {stats['fixed_blocks']}")
    print(f"  Rendered: {stats['rendered_blocks']}")
    print(f"  Failed: {stats['failed_blocks']}")
    
    if stats['issues']:
        print(f"\n  Issues fixed:")
        for issue in stats['issues']:
            print(f"    - {issue}")
    
    # Check if output file was created
    if os.path.exists(output_file):
        print(f"\n✓ Output file created successfully: {output_file}")
        with open(output_file, 'r', encoding='utf-8') as f:
            content = f.read()
        print(f"  File size: {len(content)} bytes")
        
        # Cleanup
        os.remove(input_file)
        print(f"\n✓ Test files cleaned up")
        
        return True
    else:
        print(f"\n✗ Output file was not created")
        return False

def run_all_tests():
    """Run all tests."""
    print("\n" + "="*60)
    print("LLM DIAGRAM PROCESSOR - TEST SUITE")
    print("="*60 + "\n")
    
    tests = [
        ("Code Block Detection", test_code_detection),
        ("Syntax Validation", test_syntax_validation),
        ("Full Processing", test_full_processing),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
            print()
        except Exception as e:
            print(f"\n✗ Test failed with error: {e}")
            results.append((name, False))
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    for name, result in results:
        status = "✓ PASSED" if result else "✗ FAILED"
        print(f"{status}: {name}")
    
    passed = sum(1 for _, r in results if r)
    total = len(results)
    print(f"\nTotal: {passed}/{total} tests passed")
    
    return passed == total

if __name__ == '__main__':
    success = run_all_tests()
    exit(0 if success else 1)
