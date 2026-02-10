
import subprocess
import sys
import os

def main():
    print("💬 Mr Gagger Chat Active. Type your request below.")
    print("Commands: 'Mode: Trade', 'Mode: Organize', 'Confirm', 'Cancel'")
    print("(Type 'exit' to quit)")
    
    while True:
        try:
            user_input = input("\nYou: ").strip()
            
            if not user_input:
                continue
                
            if user_input.lower() == 'exit':
                print("Goodbye!")
                break
            
            # Route through dispatcher
            # dispatcher.py is at: C:\Users\josha\OneDrive\Desktop\Clawd\dispatcher.py
            dispatcher_path = os.path.join(os.path.dirname(__file__), "..", "..", "..", "dispatcher.py")
            dispatcher_path = os.path.abspath(dispatcher_path)
            
            cmd = ["python", dispatcher_path, user_input]
            
            result = subprocess.run(cmd, capture_output=True, text=True, shell=True)
            
            if result.stdout:
                print(f"Mr Gagger: {result.stdout.strip()}")
            if result.stderr and result.returncode != 0:
                print(f"Error: {result.stderr.strip()}")
                
        except KeyboardInterrupt:
            print("\nGoodbye!")
            break
        except Exception as e:
            print(f"An error occurred: {e}")

if __name__ == "__main__":
    main()
