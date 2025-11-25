import polars as pl
import time
import random
import string
from collections import defaultdict

# Configuration
NUM_ROWS = 1_000_000
CATEGORIES = ['Electronics', 'Clothing', 'Food', 'Books', 'Toys', 'Sports', 'Home', 'Garden']
TAGS_POOL = ['popular', 'sale', 'new', 'limited', 'premium', 'bestseller', 'organic', 'imported']

print(f"Generating {NUM_ROWS:,} rows of data...")
start_gen = time.time()

# Generate data
data = {
    'id': list(range(NUM_ROWS)),
    'name': [''.join(random.choices(string.ascii_letters, k=10)) for _ in range(NUM_ROWS)],
    'category': [random.choice(CATEGORIES) for _ in range(NUM_ROWS)],
    'price': [round(random.uniform(10, 1000), 2) for _ in range(NUM_ROWS)],
    'quantity': [random.randint(1, 100) for _ in range(NUM_ROWS)],
    'tags': [random.sample(TAGS_POOL, k=random.randint(1, 4)) for _ in range(NUM_ROWS)]
}

# Create Polars DataFrame
df_polars = pl.DataFrame(data)

# Create Python list of dicts
data_python = [
    {
        'id': data['id'][i],
        'name': data['name'][i],
        'category': data['category'][i],
        'price': data['price'][i],
        'quantity': data['quantity'][i],
        'tags': data['tags'][i]
    }
    for i in range(NUM_ROWS)
]

print(f"Data generation completed in {time.time() - start_gen:.2f}s\n")
#
# # ============================================
# # BENCHMARK 1: Filter by category and price
# # ============================================
# print("=" * 60)
# print("BENCHMARK 1: Filter (category='Electronics' AND price > 500)")
# print("=" * 60)
#
# # Polars
# start = time.time()
# result_polars = df_polars.filter(
#     (pl.col('category') == 'Electronics') & (pl.col('price') > 500)
# )
# polars_time = time.time() - start
# polars_count = len(result_polars)
# print(f"Polars:      {polars_time:.4f}s - {polars_count:,} rows")
#
# # Pure Python
# start = time.time()
# result_python = [
#     row for row in data_python
#     if row['category'] == 'Electronics' and row['price'] > 500
# ]
# python_time = time.time() - start
# python_count = len(result_python)
# print(f"Pure Python: {python_time:.4f}s - {python_count:,} rows")
# print(f"Speedup:     {python_time/polars_time:.1f}x faster\n")

# ============================================
# BENCHMARK 2: Sort by price (descending)
# ============================================
# print("=" * 60)
# print("BENCHMARK 2: Sort by price (descending)")
# print("=" * 60)
#
# # Polars
# start = time.time()
# result_polars = df_polars.sort('price', descending=True)
# polars_time = time.time() - start
# print(f"Polars:      {polars_time:.4f}s")
#
# # Pure Python
# start = time.time()
# result_python = sorted(data_python, key=lambda x: x['price'], reverse=True)
# python_time = time.time() - start
# print(f"Pure Python: {python_time:.4f}s")
# print(f"Speedup:     {python_time/polars_time:.1f}x faster\n")
#
# # ============================================
# # BENCHMARK 3: Group by category, sum prices
# # ============================================
# print("=" * 60)
# print("BENCHMARK 3: Group by category, aggregate (sum, mean, count)")
# print("=" * 60)
#
# # Polars
# start = time.time()
# result_polars = df_polars.group_by('category').agg([
#     pl.col('price').sum().alias('total_price'),
#     pl.col('price').mean().alias('avg_price'),
#     pl.col('quantity').sum().alias('total_quantity'),
#     pl.len().alias('count')
# ]).sort('total_price', descending=True)
# polars_time = time.time() - start
# print(f"Polars:      {polars_time:.4f}s")
#
# # Pure Python
# start = time.time()
# groups = defaultdict(lambda: {'prices': [], 'quantities': [], 'count': 0})
# for row in data_python:
#     cat = row['category']
#     groups[cat]['prices'].append(row['price'])
#     groups[cat]['quantities'].append(row['quantity'])
#     groups[cat]['count'] += 1
#
# result_python = [
#     {
#         'category': cat,
#         'total_price': sum(data['prices']),
#         'avg_price': sum(data['prices']) / len(data['prices']),
#         'total_quantity': sum(data['quantities']),
#         'count': data['count']
#     }
#     for cat, data in groups.items()
# ]
# result_python = sorted(result_python, key=lambda x: x['total_price'], reverse=True)
# python_time = time.time() - start
# print(f"Pure Python: {python_time:.4f}s")
# print(f"Speedup:     {python_time/polars_time:.1f}x faster\n")
#
# # ============================================
# # BENCHMARK 4: Filter by tag (list contains)
# # ============================================
# print("=" * 60)
# print("BENCHMARK 4: Filter rows containing tag 'premium'")
# print("=" * 60)
#
# # Polars
# start = time.time()
# result_polars = df_polars.filter(pl.col('tags').list.contains('premium'))
# polars_time = time.time() - start
# polars_count = len(result_polars)
# print(f"Polars:      {polars_time:.4f}s - {polars_count:,} rows")
#
# # Pure Python
# start = time.time()
# result_python = [row for row in data_python if 'premium' in row['tags']]
# python_time = time.time() - start
# python_count = len(result_python)
# print(f"Pure Python: {python_time:.4f}s - {python_count:,} rows")
# print(f"Speedup:     {python_time/polars_time:.1f}x faster\n")

# ============================================
# BENCHMARK 5: Explode tags and group
# ============================================
print("=" * 60)
print("BENCHMARK 5: Explode tags, count occurrences, sort")
print("=" * 60)

# Polars
start = time.time()
result_polars = (df_polars
    .explode('tags')
    .group_by('tags')
    .agg(pl.len().alias('count'))
    .sort('count', descending=True)
)
polars_time = time.time() - start
print(f"Polars:      {polars_time:.4f}s")

# Pure Python
start = time.time()
tag_counts = defaultdict(int)
for row in data_python:
    for tag in row['tags']:
        tag_counts[tag] += 1
result_python = sorted(
    [{'tags': tag, 'count': count} for tag, count in tag_counts.items()],
    key=lambda x: x['count'],
    reverse=True
)
python_time = time.time() - start
print(f"Pure Python: {python_time:.4f}s")
print(f"Speedup:     {python_time/polars_time:.1f}x faster\n")

# ============================================
# BENCHMARK 6: Complex multi-operation pipeline
# ============================================
print("=" * 60)
print("BENCHMARK 6: Complex pipeline (filter, group, sort, limit)")
print("=" * 60)

# Polars
start = time.time()
result_polars = (df_polars
    .filter(pl.col('price') > 100)
    .group_by('category')
    .agg([
        pl.col('price').mean().alias('avg_price'),
        pl.len().alias('count')
    ])
    .filter(pl.col('count') > 10000)
    .sort('avg_price', descending=True)
    .head(5)
)
polars_time = time.time() - start
print(f"Polars:      {polars_time:.4f}s")

# Pure Python
start = time.time()
# Filter price > 100
filtered = [row for row in data_python if row['price'] > 100]
# Group by category
groups = defaultdict(list)
for row in filtered:
    groups[row['category']].append(row['price'])
# Aggregate
aggregated = [
    {'category': cat, 'avg_price': sum(prices)/len(prices), 'count': len(prices)}
    for cat, prices in groups.items()
]
# Filter count > 10000
filtered_agg = [row for row in aggregated if row['count'] > 10000]
# Sort and limit
result_python = sorted(filtered_agg, key=lambda x: x['avg_price'], reverse=True)[:5]
python_time = time.time() - start
print(f"Pure Python: {python_time:.4f}s")
print(f"Speedup:     {python_time/polars_time:.1f}x faster\n")

# ============================================
# Summary
# ============================================
print("=" * 60)
print("SUMMARY: Polars is consistently faster for data operations")
print("=" * 60)
print("Key advantages of Polars:")
print("- Optimized Rust backend with parallel execution")
print("- Lazy evaluation and query optimization")
print("- Column-oriented storage (better cache locality)")
print("- SIMD operations for numeric computations")
print("- Zero-copy operations where possible")