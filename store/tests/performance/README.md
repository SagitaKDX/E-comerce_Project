# Performance Testing Guide

This directory contains performance tests for the e-commerce application. Performance testing is crucial to ensure the application remains responsive as the dataset grows and user traffic increases.

## Test Files

- **test_performance.py**: Tests view rendering times, cart operations, and checkout processes
- **test_db_performance.py**: Tests database query efficiency, optimizations, and bulk operations

## Running Tests

To run all performance tests:

```bash
python run_performance_tests.py
```

To run a specific performance test file:

```bash
python manage.py test store.tests.performance.test_performance
```

## Interpreting Results

The performance tests output:

1. **Execution time**: How long each operation takes
2. **Query count**: How many database queries were executed
3. **Pass/fail status**: Based on predefined thresholds

Example output:
```
Home page load time: 0.0521 seconds
Number of queries: 12
```

### Performance Thresholds

Our current performance targets:

- Page loads: < 1 second
- API responses: < 500ms
- Database queries per page: < 20
- Bulk operations (100 items): < 2 seconds

## Common Performance Issues

1. **N+1 Query Problem**: Occurs when code executes one query to fetch a list of items and then executes additional queries for each item in the list.

   ```python
   # Bad (N+1 problem)
   products = Product.objects.all()
   for product in products:
       category_name = product.category.name  # Causes additional query for each product
   
   # Good (solves N+1)
   products = Product.objects.select_related('category').all()
   for product in products:
       category_name = product.category.name  # No additional queries
   ```

2. **Missing Indexes**: Not having database indexes on frequently queried fields.

3. **Inefficient Bulk Operations**: Creating/updating objects one at a time instead of in bulk.

   ```python
   # Bad (slow)
   for i in range(100):
       Product.objects.create(name=f"Product {i}", ...)
   
   # Good (fast)
   products = [Product(name=f"Product {i}", ...) for i in range(100)]
   Product.objects.bulk_create(products)
   ```

4. **Over-fetching Data**: Retrieving more data than needed.

   ```python
   # Bad (fetches all fields)
   products = Product.objects.all()
   
   # Good (only fetches needed fields)
   products = Product.objects.only('name', 'price').all()
   ```

## Best Practices

1. **Use select_related() and prefetch_related()**
   - `select_related()` for ForeignKey relationships
   - `prefetch_related()` for reverse ForeignKey and ManyToMany relationships

2. **Use database indexes**
   - Add indexes to fields frequently used in filters, ordering, or joins
   - Example: `db_index=True` in model field definition

3. **Implement caching**
   - Cache expensive database queries
   - Cache rendered template fragments
   - Use Django's cache framework

4. **Use pagination**
   - Never load all records at once in views
   - Use Django's pagination to limit records per page

5. **Optimize template rendering**
   - Use template fragment caching
   - Avoid complex logic in templates

6. **Use bulk operations**
   - `bulk_create()`, `bulk_update()`, and `bulk_delete()` for multiple records

7. **Profile regularly**
   - Run performance tests on a schedule
   - Investigate performance regressions immediately

## Extending Performance Tests

When adding new features to the application, consider:

1. Adding performance tests for new views or API endpoints
2. Testing with realistic data volumes
3. Testing critical user journeys end-to-end
4. Establishing baseline metrics and monitoring for regressions

## Tools for Further Analysis

- **Django Debug Toolbar**: Shows SQL queries, timing, and templates used for each request
- **Django Silk**: More advanced profiling tool for Django
- **New Relic / Datadog**: Production monitoring for real-world performance 