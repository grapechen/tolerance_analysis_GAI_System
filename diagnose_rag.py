from server.graph_rag import get_graph_rag_response, _triplets_context_cache

print("--- Testing RAG Engine ---")
response = get_graph_rag_response("垂直度公差的定義是什麼？")

print("\n--- LLM 最終回覆 ---")
print(response)

# 儲存一份 Context 看長怎樣
with open("context_dump.txt", "w", encoding="utf-8") as f:
    f.write(_triplets_context_cache)
print("\n[已將 Context 輸出至 context_dump.txt]")
