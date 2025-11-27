#!/usr/bin/env python
"""
Search Performance Benchmark Script
Compares Elasticsearch vs Django ORM search performance via HTTP API
"""
import os
import sys
import django
import time
import argparse
import json
import statistics
import requests
from datetime import datetime
from typing import Dict, List, Any, Optional

# Setup Django environment
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'organic_hub.settings')
django.setup()

# Import test data feeder and cleanup
from feed_test_data import TestDataFeeder
from cleanup_test_data import TestDataCleanup
from core.models import Category, CertificationOrganization

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    print("Warning: psutil not available. Memory and CPU metrics will be limited.")


try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    print("Warning: psutil not available. Memory and CPU metrics will be limited.")


class BenchmarkRunner:
    """Main benchmark runner class"""
    
    def __init__(self, iterations=10, api_base_url='http://localhost:8000'):
        self.iterations = iterations
        self.api_base_url = api_base_url.rstrip('/')
        self.process = psutil.Process(os.getpid()) if PSUTIL_AVAILABLE else None
        self.results = []
    
    def get_test_queries(self, test_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate test query cases"""
        test_cases = []
        
        categories = test_data['categories']
        certificates = test_data['certificates']
        
        # 1. Text search only - short queries
        test_cases.append({
            'name': 'Text Search - Short (rice)',
            'query': 'rice',
            'filters': None
        })
        
        test_cases.append({
            'name': 'Text Search - Short (vegetables)',
            'query': 'vegetables',
            'filters': None
        })
        
        # 2. Text search only - long queries
        test_cases.append({
            'name': 'Text Search - Long (organic rice)',
            'query': 'organic rice',
            'filters': None
        })
        
        test_cases.append({
            'name': 'Text Search - Long (fresh vegetables)',
            'query': 'fresh vegetables',
            'filters': None
        })
        
        # 3. Text search - no results
        test_cases.append({
            'name': 'Text Search - No Results',
            'query': 'xyzabc123nonexistent',
            'filters': None
        })
        
        # 4. Filters only - category
        if categories:
            test_cases.append({
                'name': 'Filter - Category Only',
                'query': None,
                'filters': {'category_id': categories[0].category_id, 'is_active': True}
            })
        
        # 5. Filters only - certificate
        if certificates:
            test_cases.append({
                'name': 'Filter - Certificate Only',
                'query': None,
                'filters': {'certificate_id': certificates[0].organization_id, 'is_active': True}
            })
        
        # 6. Filters only - price range
        test_cases.append({
            'name': 'Filter - Price Range Only',
            'query': None,
            'filters': {'min_price': 50000, 'max_price': 100000, 'is_active': True}
        })
        
        # 7. Filters only - combined filters
        if categories and certificates:
            test_cases.append({
                'name': 'Filter - Category + Certificate + Price',
                'query': None,
                'filters': {
                    'category_id': categories[0].category_id,
                    'certificate_id': certificates[0].organization_id,
                    'min_price': 50000,
                    'max_price': 200000,
                    'is_active': True
                }
            })
        
        # 8. Combined - text + category
        if categories:
            test_cases.append({
                'name': 'Combined - Text + Category',
                'query': 'rice',
                'filters': {'category_id': categories[0].category_id, 'is_active': True}
            })
        
        # 9. Combined - text + certificate
        if certificates:
            test_cases.append({
                'name': 'Combined - Text + Certificate',
                'query': 'organic',
                'filters': {'certificate_id': certificates[0].organization_id, 'is_active': True}
            })
        
        # 10. Combined - text + category + certificate + price
        if categories and certificates:
            test_cases.append({
                'name': 'Combined - Text + Category + Certificate + Price',
                'query': 'vegetables',
                'filters': {
                    'category_id': categories[0].category_id,
                    'certificate_id': certificates[0].organization_id,
                    'min_price': 30000,
                    'max_price': 150000,
                    'is_active': True
                }
            })
        
        return test_cases
    
    def benchmark_search(
        self, 
        method: str, 
        query: Optional[str], 
        filters: Optional[Dict[str, Any]], 
        iterations: int = 10
    ) -> Dict[str, Any]:
        """Benchmark a single search method via HTTP API"""
        execution_times = []
        memory_usages = []
        cpu_usages = []
        result_counts = []
        
        # Build API URL
        api_url = f"{self.api_base_url}/search/api/"
        
        # Build query parameters
        params = {}
        if query:
            params['q'] = query
        if filters:
            if filters.get('category_id'):
                params['category_id'] = filters['category_id']
            if filters.get('certificate_id'):
                params['certificate_id'] = filters['certificate_id']
            if filters.get('min_price'):
                params['min_price'] = filters['min_price']
            if filters.get('max_price'):
                params['max_price'] = filters['max_price']
        params['size'] = 1000  # Request up to 1000 results
        
        # Warm up
        try:
            response = requests.get(api_url, params=params, timeout=30)
            response.raise_for_status()
        except:
            pass
        
        for i in range(iterations):
            # Measure memory before
            if self.process:
                memory_before = self.process.memory_info().rss / 1024 / 1024  # MB
                cpu_before = self.process.cpu_percent(interval=0.1)
            
            # Measure execution time
            start_time = time.perf_counter()
            
            try:
                # Send HTTP request to API
                response = requests.get(api_url, params=params, timeout=30)
                response.raise_for_status()
                
                data = response.json()
                execution_time = time.perf_counter() - start_time
                result_count = data.get('count', 0)
                
            except Exception as e:
                execution_time = time.perf_counter() - start_time
                result_count = 0
                if i == 0:  # Only log error on first iteration
                    print(f"  ⚠ Error in {method}: {str(e)}")
            
            # Measure memory after
            if self.process:
                memory_after = self.process.memory_info().rss / 1024 / 1024  # MB
                cpu_after = self.process.cpu_percent(interval=0.1)
                memory_usage = memory_after - memory_before
                cpu_usage = cpu_after - cpu_before
            else:
                memory_usage = 0
                cpu_usage = 0
            
            execution_times.append(execution_time)
            memory_usages.append(memory_usage)
            cpu_usages.append(cpu_usage)
            result_counts.append(result_count)
        
        # Calculate statistics
        return {
            'method': method,
            'execution_time': {
                'mean': statistics.mean(execution_times),
                'median': statistics.median(execution_times),
                'min': min(execution_times),
                'max': max(execution_times),
                'stdev': statistics.stdev(execution_times) if len(execution_times) > 1 else 0,
                'values': execution_times
            },
            'memory_usage': {
                'mean': statistics.mean(memory_usages) if memory_usages else 0,
                'median': statistics.median(memory_usages) if memory_usages else 0,
                'min': min(memory_usages) if memory_usages else 0,
                'max': max(memory_usages) if memory_usages else 0,
                'stdev': statistics.stdev(memory_usages) if len(memory_usages) > 1 else 0,
                'values': memory_usages
            },
            'cpu_usage': {
                'mean': statistics.mean(cpu_usages) if cpu_usages else 0,
                'median': statistics.median(cpu_usages) if cpu_usages else 0,
                'min': min(cpu_usages) if cpu_usages else 0,
                'max': max(cpu_usages) if cpu_usages else 0,
                'stdev': statistics.stdev(cpu_usages) if len(cpu_usages) > 1 else 0,
                'values': cpu_usages
            },
            'result_count': {
                'mean': statistics.mean(result_counts),
                'values': result_counts
            }
        }
    
    def run_benchmarks(self, test_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Run all benchmark tests"""
        test_cases = self.get_test_queries(test_data)
        all_results = []
        
        print(f"\n{'='*60}")
        print(f"Running benchmarks ({len(test_cases)} test cases, {self.iterations} iterations each)...")
        print(f"{'='*60}\n")
        
        for idx, test_case in enumerate(test_cases, 1):
            print(f"[{idx}/{len(test_cases)}] {test_case['name']}...")
            
            # Both methods use the same API endpoint (Elasticsearch with fallback)
            # We'll test the API endpoint which uses Elasticsearch with Django ORM fallback
            print("  → API Endpoint (Elasticsearch with fallback)...", end=" ", flush=True)
            try:
                api_result = self.benchmark_search('api', test_case['query'], test_case['filters'], self.iterations)
                print(f"✓ ({api_result['execution_time']['mean']:.4f}s)")
            except Exception as e:
                print(f"✗ Error: {str(e)}")
                api_result = None
            
            all_results.append({
                'test_case': test_case,
                'api': api_result
            })
        
        return all_results
    
    def generate_html_report(self, results: List[Dict[str, Any]], output_file: str = 'benchmark_report.html'):
        """Generate HTML report with charts and tables"""
        print(f"\n{'='*60}")
        print(f"Generating HTML report: {output_file}")
        print(f"{'='*60}\n")
        
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # Prepare data for charts
        chart_data = {
            'labels': [],
            'api_times': [],
            'api_memory': [],
            'api_cpu': []
        }
        
        for result in results:
            test_name = result['test_case']['name']
            chart_data['labels'].append(test_name)
            
            if result.get('api'):
                chart_data['api_times'].append(result['api']['execution_time']['mean'] * 1000)  # Convert to ms
                chart_data['api_memory'].append(result['api']['memory_usage']['mean'])
                chart_data['api_cpu'].append(result['api']['cpu_usage']['mean'])
            else:
                chart_data['api_times'].append(0)
                chart_data['api_memory'].append(0)
                chart_data['api_cpu'].append(0)
        
        html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Search Performance Benchmark Report</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            margin: 0;
            padding: 20px;
            background-color: #f5f5f5;
        }}
        .container {{
            max-width: 1400px;
            margin: 0 auto;
            background: white;
            padding: 30px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        h1 {{
            color: #333;
            border-bottom: 3px solid #4CAF50;
            padding-bottom: 10px;
        }}
        h2 {{
            color: #555;
            margin-top: 30px;
        }}
        .summary {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin: 20px 0;
        }}
        .summary-card {{
            background: #f9f9f9;
            padding: 15px;
            border-radius: 5px;
            border-left: 4px solid #4CAF50;
        }}
        .summary-card h3 {{
            margin: 0 0 10px 0;
            color: #333;
            font-size: 14px;
            text-transform: uppercase;
        }}
        .summary-card .value {{
            font-size: 24px;
            font-weight: bold;
            color: #4CAF50;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
        }}
        th, td {{
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }}
        th {{
            background-color: #4CAF50;
            color: white;
            font-weight: 600;
        }}
        tr:hover {{
            background-color: #f5f5f5;
        }}
        .chart-container {{
            margin: 30px 0;
            height: 400px;
            position: relative;
        }}
        .faster {{
            color: #4CAF50;
            font-weight: bold;
        }}
        .slower {{
            color: #f44336;
            font-weight: bold;
        }}
        .footer {{
            margin-top: 40px;
            padding-top: 20px;
            border-top: 1px solid #ddd;
            color: #666;
            font-size: 12px;
            text-align: center;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Search Performance Benchmark Report</h1>
        <p><strong>Generated:</strong> {timestamp}</p>
        
        <h2>Summary</h2>
        <div class="summary">
            <div class="summary-card">
                <h3>Total Test Cases</h3>
                <div class="value">{len(results)}</div>
            </div>
            <div class="summary-card">
                <h3>Iterations per Test</h3>
                <div class="value">{self.iterations}</div>
            </div>
        </div>
        
        <h2>Execution Time (ms)</h2>
        <div class="chart-container">
            <canvas id="timeChart"></canvas>
        </div>
        
        <h2>Memory Usage (MB)</h2>
        <div class="chart-container">
            <canvas id="memoryChart"></canvas>
        </div>
        
        <h2>CPU Usage (%)</h2>
        <div class="chart-container">
            <canvas id="cpuChart"></canvas>
        </div>
        
        <h2>Detailed Results</h2>
        <table>
            <thead>
                <tr>
                    <th>Test Case</th>
                    <th>Method</th>
                    <th>Avg Time (ms)</th>
                    <th>Min Time (ms)</th>
                    <th>Max Time (ms)</th>
                    <th>Memory (MB)</th>
                    <th>CPU (%)</th>
                    <th>Results</th>
                </tr>
            </thead>
            <tbody>
"""
        
        for result in results:
            test_name = result['test_case']['name']
            query_info = f"Query: {result['test_case']['query'] or 'N/A'}"
            filters_info = f"Filters: {json.dumps(result['test_case']['filters']) if result['test_case']['filters'] else 'None'}"
            
            # API row
            if result.get('api'):
                api = result['api']
                api_time_ms = api['execution_time']['mean'] * 1000
                api_memory = api['memory_usage']['mean']
                api_cpu = api['cpu_usage']['mean']
                api_results = int(api['result_count']['mean'])
                html_content += f"""
                <tr>
                    <td><strong>{test_name}</strong><br><small>{query_info}<br>{filters_info}</small></td>
                    <td><span style="color: #2196F3;">API Endpoint</span></td>
                    <td>{api_time_ms:.2f}</td>
                    <td>{api['execution_time']['min']*1000:.2f}</td>
                    <td>{api['execution_time']['max']*1000:.2f}</td>
                    <td>{api_memory:.2f}</td>
                    <td>{api_cpu:.2f}</td>
                    <td>{api_results}</td>
                </tr>
"""
            else:
                html_content += f"""
                <tr>
                    <td><strong>{test_name}</strong><br><small>{query_info}<br>{filters_info}</small></td>
                    <td><span style="color: #2196F3;">API Endpoint</span></td>
                    <td colspan="6" style="color: #f44336;">Error or not available</td>
                </tr>
"""
        
        html_content += """
            </tbody>
        </table>
        
        <div class="footer">
            <p>Generated by Search Performance Benchmark Script</p>
        </div>
    </div>
    
    <script>
        // Chart.js configuration
        const chartOptions = {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                y: {
                    beginAtZero: true
                }
            },
            plugins: {
                legend: {
                    display: true,
                    position: 'top'
                }
            }
        };
        
        // Execution Time Chart
        const timeCtx = document.getElementById('timeChart').getContext('2d');
        new Chart(timeCtx, {
            type: 'bar',
            data: {
                labels: """ + json.dumps(chart_data['labels']) + """,
                datasets: [{
                    label: 'API Endpoint',
                    data: """ + json.dumps(chart_data['api_times']) + """,
                    backgroundColor: 'rgba(33, 150, 243, 0.7)',
                    borderColor: 'rgba(33, 150, 243, 1)',
                    borderWidth: 1
                }]
            },
            options: chartOptions
        });
        
        // Memory Usage Chart
        const memoryCtx = document.getElementById('memoryChart').getContext('2d');
        new Chart(memoryCtx, {
            type: 'bar',
            data: {
                labels: """ + json.dumps(chart_data['labels']) + """,
                datasets: [{
                    label: 'API Endpoint',
                    data: """ + json.dumps(chart_data['api_memory']) + """,
                    backgroundColor: 'rgba(33, 150, 243, 0.7)',
                    borderColor: 'rgba(33, 150, 243, 1)',
                    borderWidth: 1
                }]
            },
            options: chartOptions
        });
        
        // CPU Usage Chart
        const cpuCtx = document.getElementById('cpuChart').getContext('2d');
        new Chart(cpuCtx, {
            type: 'bar',
            data: {
                labels: """ + json.dumps(chart_data['labels']) + """,
                datasets: [{
                    label: 'API Endpoint',
                    data: """ + json.dumps(chart_data['api_cpu']) + """,
                    backgroundColor: 'rgba(33, 150, 243, 0.7)',
                    borderColor: 'rgba(33, 150, 243, 1)',
                    borderWidth: 1
                }]
            },
            options: chartOptions
        });
    </script>
</body>
</html>
"""
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        print(f"✓ Report generated: {output_file}")


def main():
    parser = argparse.ArgumentParser(description='Benchmark search API performance via HTTP requests')
    parser.add_argument('--num-products', type=int, default=1000, help='Number of products to create (default: 1000)')
    parser.add_argument('--num-stores', type=int, default=10, help='Number of stores to create (default: 10)')
    parser.add_argument('--num-categories', type=int, default=5, help='Number of categories to create (default: 5)')
    parser.add_argument('--num-certificates', type=int, default=3, help='Number of certificates to create (default: 3)')
    parser.add_argument('--iterations', type=int, default=10, help='Number of iterations per test (default: 10)')
    parser.add_argument('--output', type=str, default='benchmark_report.html', help='Output HTML file (default: benchmark_report.html)')
    parser.add_argument('--keep-data', action='store_true', help='Keep test data after benchmark')
    parser.add_argument('--skip-indexing', action='store_true', help='Skip Elasticsearch indexing')
    parser.add_argument('--api-url', type=str, default='http://localhost:8000', help='Base URL for API (default: http://localhost:8000)')
    parser.add_argument('--use-existing-data', action='store_true', help='Use existing test data in database (skip data creation)')
    
    args = parser.parse_args()
    
    runner = BenchmarkRunner(iterations=args.iterations, api_base_url=args.api_url)
    feeder = TestDataFeeder()
    
    try:
        # Create or use existing test data
        if args.use_existing_data:
            print(f"\n{'='*60}")
            print("Using existing test data from database...")
            print(f"{'='*60}\n")
            # Get test data from database
            from core.models import CustomUser, Store, Product
            test_user = CustomUser.objects.filter(phone_number='+84900000000').first()
            if not test_user:
                print("Error: No existing test data found. Please run feed_test_data.py first.")
                sys.exit(1)
            
            test_stores = Store.objects.filter(user=test_user, store_name__startswith='Test Store')
            test_products = Product.objects.filter(store__in=test_stores, SKU__startswith='SKU-')
            test_categories = Category.objects.filter(product__in=test_products).distinct()
            test_certificates = CertificationOrganization.objects.filter(
                storeverificationrequest__store__in=test_stores
            ).distinct()
            
            test_data = {
                'users': [test_user],
                'stores': list(test_stores),
                'categories': list(test_categories),
                'certificates': list(test_certificates),
                'products': list(test_products),
                'verification_requests': [],
                'store_certifications': []
            }
            print(f"Found {len(test_data['products'])} products, {len(test_data['stores'])} stores")
        else:
            # Warn user about large datasets
            if args.num_products >= 50000:
                print(f"\n{'='*60}")
                print("⚠ WARNING: Large dataset detected!")
                print(f"{'='*60}")
                print(f"Creating {args.num_products:,} products may take significant time and memory.")
                print("Estimated time: 10-30 minutes depending on your system.")
                print(f"{'='*60}\n")
                
                response = input("Continue? (yes/no): ")
                if response.lower() not in ['yes', 'y']:
                    print("Aborted.")
                    sys.exit(0)
            
            # Create test data using feeder
            test_data = feeder.create_test_data(
                args.num_products,
                args.num_stores,
                args.num_categories,
                args.num_certificates
            )
            
            # Index products into Elasticsearch
            feeder.index_to_elasticsearch(test_data, skip_indexing=args.skip_indexing)
        
        # Run benchmarks
        results = runner.run_benchmarks(test_data)
        
        # Generate report
        runner.generate_html_report(results, args.output)
        
        # Cleanup
        if not args.keep_data and not args.use_existing_data:
            cleanup = TestDataCleanup()
            cleanup.cleanup_test_data(test_data, keep_data=False)
        
        print(f"\n{'='*60}")
        print("Benchmark completed successfully!")
        print(f"{'='*60}\n")
        
    except KeyboardInterrupt:
        print("\n\nBenchmark interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nError during benchmark: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()

