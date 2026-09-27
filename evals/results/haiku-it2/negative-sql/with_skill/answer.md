Ось SQL-запит для підрахунку DAU за останні 30 днів з таблиці events:

```sql
SELECT COUNT(DISTINCT user_id) AS dau
FROM events
WHERE ts >= CURRENT_DATE - INTERVAL '30 days'
```

Якщо вам потрібно DAU для кожного дня окремо за останні 30 днів:

```sql
SELECT 
  DATE(ts) AS date,
  COUNT(DISTINCT user_id) AS dau
FROM events
WHERE ts >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY DATE(ts)
ORDER BY date DESC;
```

Перший запит повертає одне число - загальну кількість унікальних користувачів, активних за останні 30 днів.

Другий запит показує DAU для кожного дня, що дозволяє бачити тренди активності.
