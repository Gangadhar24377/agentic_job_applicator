from job_search import JobSearchTool

def test_job_search():
    # Create the search tool
    searcher = JobSearchTool()
    
    print("Testing with 'query' parameter...")
    try:
        result1 = searcher._run(query="Software Engineer", limit=2)
        print(f"Success! Found {len(result1)} jobs")
    except Exception as e:
        print(f"Error with 'query' parameter: {str(e)}")
    
    print("\nTesting with 'search_query' parameter...")
    try:
        result2 = searcher._run(search_query="Software Engineer", limit=2)
        print(f"Success! Found {len(result2)} jobs")
    except Exception as e:
        print(f"Error with 'search_query' parameter: {str(e)}")
    
    print("\nTesting with direct function...")
    try:
        from tool_functions import search_jobs
        result3 = search_jobs("Software Engineer")
        print(f"Success! Found {len(result3)} jobs")
    except Exception as e:
        print(f"Error with direct function: {str(e)}")
    
    print("\nTesting with dictionary input...")
    try:
        from tool_functions import search_jobs
        result4 = search_jobs({"search_query": "Software Engineer", "limit": 2})
        print(f"Success! Found {len(result4)} jobs")
    except Exception as e:
        print(f"Error with dictionary input: {str(e)}")

if __name__ == "__main__":
    test_job_search()