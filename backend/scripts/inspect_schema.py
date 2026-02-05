import os
import sys
from dotenv import load_dotenv

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.observability import supabase

def inspect_schema():
    print("Inspecting 'edges' table columns...")
    try:
        # Query information_schema for columns of 'edges' table
        # Note: We use rpc 'exec_sql' if available, otherwise we try to infer from data or use a standard select
        # Standard select with count=exact shows counts, but we want column names.
        
        # We can try to get one row to see keys
        res = supabase.table("edges").select("*").limit(1).execute()
        if res.data:
            print(f"Columns in 'edges': {list(res.data[0].keys())}")
        else:
            print("Table 'edges' is empty, cannot infer columns from data.")
            
        # Try to use a common RPC if it exists to list columns
        # SELECT column_name FROM information_schema.columns WHERE table_name = 'edges'
        # Since I don't know if 'exec_sql' exists (earlier search failed), I'll try to find any RPC that returns schema
        
    except Exception as e:
        print(f"Error inspecting table: {e}")

if __name__ == "__main__":
    load_dotenv()
    inspect_schema()
