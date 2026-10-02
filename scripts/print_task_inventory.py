import sys
import json

def main():
    start = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    end = int(sys.argv[2]) if len(sys.argv) > 2 else 50
    with open('tasks_inventory.json', 'r', encoding='utf-8') as f:
        tasks = json.load(f)

    for i in range(start - 1, min(end, len(tasks))):
        t = tasks[i]
        dl = [l for l in t['diff'].splitlines() if (l.startswith('+') or l.startswith('-')) and not l.startswith('---') and not l.startswith('+++')]
        print(f"[{i+1:02d}] {t['id']}")
        print(f"     Desc: {t['desc']}")
        print(f"     Changes: {dl}")

if __name__ == '__main__':
    main()
