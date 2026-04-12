import json
import os

config_file = "config.json"
if os.path.exists(config_file):
    print(f"Checking {config_file}...")
    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            content = f.read()
            print(f"File size: {len(content)} bytes")
            print(f"Lines: {len(content.splitlines())}")
            # Try to parse
            data = json.loads(content)
            print("✅ JSON is valid.")
    except Exception as e:
        print(f"❌ JSON Error: {e}")
        # Show the lines around the error
        if "line" in str(e):
            import re
            m = re.search(r'line (\d+)', str(e))
            if m:
                line_num = int(m.group(1))
                lines = content.splitlines()
                start = max(0, line_num - 5)
                end = min(len(lines), line_num + 5)
                for i in range(start, end):
                    marker = ">>>" if i + 1 == line_num else "   "
                    print(f"{marker} {i+1}: {lines[i]}")
else:
    print("config.json not found in root.")
