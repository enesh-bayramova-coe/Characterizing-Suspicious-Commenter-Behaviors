from typing import Callable, Dict, List, Optional, Any
import collections
import datetime
import heapq
import re

from googleapiclient.discovery import build
from api import API_KEY

DEFAULT_CSV = "comments_data.csv"
MAX_COMMENTS = 10000

DEFAULT_SPAM_PATTERN = [
    "subscribe", "whatsapp", "wa.me", "telegram", "t.me", 
    "crypto", "bitcoin", "invest", "profit", "free gift",
    "click the link", "sub for sub", "sub4sub", "my channel"
]

DEFAULT_FREQ_THRESHOLD = 2
YOUTUBE_API_SERVICE_NAME = "youtube"
YOUTUBE_API_VERSION = "v3"


def extract_video_id(video_input: str) -> str:

    # Extract the YouTube video ID from a raw ID or full URL.

    video_input = video_input.strip()
    if not video_input:
        raise ValueError("Please enter a valid YouTube video ID or URL.")

    patterns = [
        r"(?:v=|vi=)([A-Za-z0-9_-]{11})",
        r"(?:youtu\.be/)([A-Za-z0-9_-]{11})",
        r"(?:embed/)([A-Za-z0-9_-]{11})",
        r"^([A-Za-z0-9_-]{11})$",
    ]
    for pattern in patterns:
        match = re.search(pattern, video_input)
        if match:
            return match.group(1)
    raise ValueError("Invalid YouTube video ID or URL. Use the short ID or full video link.")


def fetch_youtube_comments(video_id: str, max_results: int = 1000) -> List[Dict[str, Any]]:

    #Fetch up to max_results top-level comments for a YouTube video

    youtube = build(YOUTUBE_API_SERVICE_NAME, YOUTUBE_API_VERSION, developerKey=API_KEY)
    parsed_data: List[Dict[str, Any]] = []
    frequency_map: Dict[str, int] = {}
    next_page_token = None

    while len(parsed_data) < max_results:
        remaining = max_results - len(parsed_data)
        request = youtube.commentThreads().list(
            part="snippet",
            videoId=video_id,
            maxResults=min(100, remaining),
            textFormat="plainText",
            pageToken=next_page_token,
        )
        response = request.execute()

        for item in response.get("items", []):
            snippet = item["snippet"]["topLevelComment"]["snippet"]
            dt_obj = datetime.datetime.strptime(snippet["publishedAt"], "%Y-%m-%dT%H:%M:%SZ")
            timestamp = int(dt_obj.timestamp())
            account_id = snippet.get("authorChannelId", {}).get("value", snippet.get("authorDisplayName"))
            frequency_map[account_id] = frequency_map.get(account_id, 0) + 1
            parsed_data.append({
                "account_id": account_id,
                "author": snippet["authorDisplayName"],
                "text": snippet["textDisplay"],
                "timestamp": timestamp,
            })

        next_page_token = response.get("nextPageToken")
        if not next_page_token:
            break

    for row in parsed_data:
        row["post_frequency"] = frequency_map[row["account_id"]]

    return parsed_data


def sort_comments(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    # Sort comments by frequency descending, then timestamp ascending.
    return sorted(rows, key=lambda row: (-row["post_frequency"], row["timestamp"]))


def detect_outliers(sorted_data: List[Dict[str, Any]], freq_threshold: int = DEFAULT_FREQ_THRESHOLD) -> set:
    # Flag accounts with unusually high comment frequency.
    return {row["account_id"] for row in sorted_data if row["post_frequency"] >= freq_threshold}


def normalize_text(text: str) -> List[str]:
    return [token for token in text.lower().split() if token]


def jaccard_similarity(tokens_a: set, tokens_b: set) -> float:
    if not tokens_a or not tokens_b:
        return 0.0
    intersection = tokens_a & tokens_b
    union = tokens_a | tokens_b
    return len(intersection) / len(union)


def contains_pattern(text: str, pattern: Any) -> bool:
    text = text.lower()
    if not pattern:
        return False
    if isinstance(pattern, list):
        return any(pat and pat.lower() in text for pat in pattern)
    return pattern.lower() in text


def has_burst(timestamps: List[int], window_seconds: int = 60, min_count: int = 2) -> bool:
    times = sorted(timestamps)
    left = 0
    for right in range(len(times)):
        while times[right] - times[left] > window_seconds:
            left += 1
        if right - left + 1 >= min_count:
            return True
    return False


class Graph:
    def __init__(self) -> None:
        self.adj_list: Dict[str, List[tuple]] = collections.defaultdict(list)
        self.edges: List[tuple] = []
        self.vertices: set = set()

    def add_edge(self, u: str, v: str, weight: int = 1) -> None:
        self.adj_list[u].append((v, weight))
        self.adj_list[v].append((u, weight))
        self.edges.append((weight, u, v))
        self.vertices.update([u, v])


def bfs_connected_components(graph: Graph) -> List[List[str]]:
    visited = set()
    components: List[List[str]] = []
    for vertex in graph.vertices:
        if vertex not in visited:
            queue = collections.deque([vertex])
            visited.add(vertex)
            component: List[str] = []
            while queue:
                node = queue.popleft()
                component.append(node)
                for neighbor, _ in graph.adj_list[node]:
                    if neighbor not in visited:
                        visited.add(neighbor)
                        queue.append(neighbor)
            components.append(component)
    return components


def find(parent: Dict[str, str], i: str) -> str:
    if parent[i] == i:
        return i
    parent[i] = find(parent, parent[i])
    return parent[i]


def union(parent: Dict[str, str], rank: Dict[str, int], x: str, y: str) -> None:
    xroot = find(parent, x)
    yroot = find(parent, y)
    if rank[xroot] < rank[yroot]:
        parent[xroot] = yroot
    elif rank[xroot] > rank[yroot]:
        parent[yroot] = xroot
    else:
        parent[yroot] = xroot
        rank[xroot] += 1


def kruskals_mst(graph: Graph) -> List[tuple]:
    result: List[tuple] = []
    i = e = 0
    sorted_edges = sorted(graph.edges, key=lambda item: item[0])
    parent: Dict[str, str] = {node: node for node in graph.vertices}
    rank: Dict[str, int] = {node: 0 for node in graph.vertices}
    while e < len(graph.vertices) - 1 and i < len(sorted_edges):
        w, u, v = sorted_edges[i]
        i += 1
        x = find(parent, u)
        y = find(parent, v)
        if x != y:
            e += 1
            result.append((u, v, w))
            union(parent, rank, x, y)
    return result


def dijkstra(graph: Graph, start: str) -> Dict[str, float]:
    distances = {vertex: float("infinity") for vertex in graph.vertices}
    distances[start] = 0.0
    priority_queue: List[tuple] = [(0.0, start)]
    while priority_queue:
        current_distance, current_vertex = heapq.heappop(priority_queue)
        if current_distance > distances[current_vertex]:
            continue
        for neighbor, weight in graph.adj_list[current_vertex]:
            distance = current_distance + weight
            if distance < distances[neighbor]:
                distances[neighbor] = distance
                heapq.heappush(priority_queue, (distance, neighbor))
    return distances


def build_similarity_graph(sorted_data: List[Dict[str, Any]]) -> Graph:
    g = Graph()
    tokens_by_index: List[set] = []
    account_ids: List[str] = []
    index_by_token: Dict[str, set] = collections.defaultdict(set)

    for idx, row in enumerate(sorted_data):
        account_ids.append(row["account_id"])
        tokens = set(normalize_text(row["text"]))
        tokens_by_index.append(tokens)
        for token in tokens:
            index_by_token[token].add(idx)

    for i, tokens_i in enumerate(tokens_by_index):
        candidate_indices = set()
        for token in tokens_i:
            candidate_indices.update(index_by_token[token])
        for j in sorted(candidate_indices):
            if j <= i:
                continue
            if account_ids[i] == account_ids[j]:
                continue
            similarity = jaccard_similarity(tokens_i, tokens_by_index[j])
            if similarity > 0.75:
                g.add_edge(account_ids[i], account_ids[j], weight=1)
    return g


def detect_suspicious_accounts(sorted_data: List[Dict[str, Any]],
                               spam_pattern: str = DEFAULT_SPAM_PATTERN) -> Dict[str, Any]:
    suspicious_accounts = set()
    account_timestamps: Dict[str, List[int]] = {}
    for row in sorted_data:
        account = row["account_id"]
        text = row["text"]
        timestamp = row["timestamp"]
        account_timestamps.setdefault(account, []).append(timestamp)
        if contains_pattern(text, spam_pattern):
            suspicious_accounts.add(account)
    for account, times in account_timestamps.items():
        if has_burst(times):
            suspicious_accounts.add(account)
    return {
        "suspicious_accounts": suspicious_accounts,
        "account_timestamps": account_timestamps,
    }


def analyze_network(sorted_data: List[Dict[str, Any]],
                    suspicious_accounts: set) -> Dict[str, Any]:
    g = build_similarity_graph(sorted_data)
    if len(g.vertices) == 0:
        return {
            "graph": g,
            "components": [],
            "mst": [],
            "distances": {},
            "reference_bot": None,
        }
    components = bfs_connected_components(g)
    mst = kruskals_mst(g)
    distances: Dict[str, float] = {}
    reference_bot = next((acc for acc in suspicious_accounts if acc in g.vertices), None)
    if reference_bot:
        distances = dijkstra(g, reference_bot)
    return {
        "graph": g,
        "components": components,
        "mst": mst,
        "distances": distances,
        "reference_bot": reference_bot,
    }


def run_pipeline(video_id: str,
                 max_comments: int,
                 csv_file: str = DEFAULT_CSV,
                 spam_pattern: str = DEFAULT_SPAM_PATTERN,
                 freq_threshold: int = DEFAULT_FREQ_THRESHOLD,
                 stage_callback: Optional[Callable[[str], None]] = None) -> Dict[str, Any]:
    if max_comments < 1 or max_comments > MAX_COMMENTS:
        raise ValueError(f"max_comments must be between 1 and {MAX_COMMENTS}")

    video_id = extract_video_id(video_id)
    if stage_callback:
        stage_callback("Starting stage 1/4: fetching comments...")
    raw_data = fetch_youtube_comments(video_id, max_results=max_comments)
    if not raw_data:
        raise ValueError("No comments were fetched. Check the video ID, comment availability, and API access.")

    if stage_callback:
        stage_callback("Starting stage 2/4: preprocessing and sorting...")
    sorted_data = sort_comments(raw_data)
    outliers = detect_outliers(sorted_data, freq_threshold=freq_threshold)

    account_names: Dict[str, str] = {}
    account_examples: Dict[str, str] = {}
    for row in sorted_data:
        account_id = row["account_id"]
        account_names.setdefault(account_id, row["author"])
        account_examples.setdefault(account_id, row["text"])

    if stage_callback:
        stage_callback("Starting stage 3/4: content and behavior analysis...")
    behavior_output = detect_suspicious_accounts(sorted_data, spam_pattern=spam_pattern)
    suspicious_accounts = set(outliers) | behavior_output["suspicious_accounts"]
    suspicious_bots = [
        {
            "account_id": account,
            "author": account_names.get(account, account),
            "example_comment": account_examples.get(account, ""),
        }
        for account in sorted(suspicious_accounts)
    ]

    if stage_callback:
        stage_callback("Starting stage 4/4: network analysis...")
    network_output = analyze_network(sorted_data, suspicious_accounts)

    return {
        "video_id": video_id,
        "comments_fetched": len(raw_data),
        "outliers": sorted(outliers),
        "suspicious_accounts": [bot["author"] for bot in suspicious_bots],
        "suspicious_bots": suspicious_bots,
        "graph_components": network_output["components"],
        "mst": network_output["mst"],
        "distances": network_output["distances"],
        "reference_bot": network_output["reference_bot"],
    }


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python pipeline.py <VIDEO_ID> [COMMENTS_COUNT]")
        sys.exit(1)
    video_id = sys.argv[1]
    max_comments = int(sys.argv[2]) if len(sys.argv) > 2 else MAX_COMMENTS

    def stage_print(message: str) -> None:
        print(message)

    result = run_pipeline(video_id, max_comments, stage_callback=stage_print)
    print(f"Done. Detected {len(result['suspicious_accounts'])} suspicious accounts.")
