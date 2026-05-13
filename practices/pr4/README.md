# Аномалии изоляции в SQL

Средневековые алхимические рецепты.  
Dirty read — MySQL 8.0. Остальные аномалии — PostgreSQL 15. Docker.

## Запуск

```bash
docker compose down -v && docker compose up --build
```

После прогона логи транзакций по каждой аномалии лежат в [results/](results/).

## Схема и данные

Таблицы: `alchemist`, `manuscript`, `ingredient`, `activity`, `activity_ingredient` (см. [init.sql](init.sql) для PostgreSQL, [init_mysql.sql](init_mysql.sql) для MySQL).

Несколько строк для контекста:

| таблица | пример строки |
|---|---|
| alchemist | `гермогор безголовый, богемия, 1142–1219` |
| manuscript | `кодекс семидесяти трёх отговорок, 1198, латынь` |
| ingredient | `слюна одноногой жабы — усиливает уныние, пахнет вторником` |
| activity | `превращение овса в чугун → получили мягкий стыд, 14 дней` |

## Что воспроизведено

| # | Аномалия | СУБД | Воспроизводится при | Лечится | Лог |
|---|---|---|---|---|---|
| 1 | dirty read | MySQL 8.0 | read uncommitted | read committed | [01_dirty_read.log](results/01_dirty_read.log) |
| 2 | non-repeatable read | PostgreSQL 15 | read committed | repeatable read | [02_non_repeatable_read.log](results/02_non_repeatable_read.log) |
| 3 | phantom read | PostgreSQL 15 | read committed | repeatable read (snapshot isolation) | [03_phantom_read.log](results/03_phantom_read.log) |
| 4 | lost update | PostgreSQL 15 | read committed без блокировок | `select ... for update` | [04_lost_update.log](results/04_lost_update.log) |

## 1. Dirty read

PostgreSQL не поддерживает `read uncommitted` и молча повышает его до `read committed`, поэтому аномалия там невоспроизводима. Для демонстрации используется MySQL 8.0.

Шаги:
1. T1: `set session transaction isolation level read uncommitted`, `start transaction`
2. T2: `start transaction`, `update activity set duration_days = 999 where id = 1` (без commit)
3. T1: `select duration_days from activity where id = 1` → **999** (грязное чтение)
4. T2: `rollback`
5. T1: `select ...` → **14** (откат виден)

Результат ([01_dirty_read.log](results/01_dirty_read.log)):

```
[T1] set session transaction isolation level read uncommitted
[T1] start transaction
[T2] start transaction
[T2] update activity set duration_days = 999 where id = 1
[T1] select duration_days from activity where id = 1
[T1] -> ((999,),)
[T2] rollback
[T1] select duration_days from activity where id = 1
[T1] -> ((14,),)
[T1] commit
```

T1 прочитал незакоммиченные 999. После отката T2 значение вернулось в 14.

**Как избежать.** Использовать уровень изоляции не ниже `read committed`. Это минимум во всех современных СУБД.

## 2. Non-repeatable read

T1 читает строку дважды, между чтениями другая транзакция меняет ту же строку и коммитит, и T1 видит другое значение.

Воспроизведение, `read committed`:
1. T1: `begin`, `select duration_days from activity where id = 2` → **40**
2. T2: `update activity set duration_days = 77 where id = 2`, `commit`
3. T1: `select duration_days from activity where id = 2` → **77**

Лечение, `repeatable read`:
1. T1: `begin isolation level repeatable read`, `select ...` → **40**
2. T2: `update ... = 123` (autocommit)
3. T1: `select ...` → **40**

Полный лог: [02_non_repeatable_read.log](results/02_non_repeatable_read.log).

```
--- read committed ---
[T1] -> [(40,)]
[T2] update activity set duration_days = 77 where id = 2
[T2] commit
[T1] -> [(77,)]

--- repeatable read ---
[T1] -> [(40,)]
[T2] update activity set duration_days = 123 where id = 2
[T1] -> [(40,)]
```

**Как избежать.** Поднять уровень транзакции до `repeatable read`. T1 работает со снимком данных на момент `begin`. Альтернатива — `select ... for share` или `select ... for update` на нужную строку.

## 3. Phantom read

T1 дважды считает строки, между чтениями другая транзакция вставляет строку, и множество результатов внутри T1 меняется.

Воспроизведение, `read committed`:
1. T1: `begin`, `select count(*) from activity where alchemist_id = 1` → **2**
2. T2: `insert into activity ... 'фантомная активность' ...` (autocommit)
3. T1: `select count(*) ...` → **3**

Лечение, `repeatable read`:
1. T1: `begin isolation level repeatable read`, `select count(*)` → **2**
2. T2: `insert ...` (autocommit)
3. T1: `select count(*)` → **2**

Полный лог: [03_phantom_read.log](results/03_phantom_read.log).

```
--- read committed ---
[T1] -> [(2,)]
[T2] insert into activity ... 'фантомная активность' ...
[T1] -> [(3,)]

--- repeatable read ---
[T1] -> [(2,)]
[T2] insert into activity ... 'фантомная активность' ...
[T1] -> [(2,)]
```

**Как избежать.** В PostgreSQL фантомы устраняются уже на `repeatable read` за счёт snapshot isolation. По стандарту SQL для этого требуется `serializable`.

## 4. Lost update

Две транзакции читают одно значение, считают новое и записывают. Вторая запись затирает первую.

Воспроизведение, `read committed` без блокировок (T1 хочет `+5`, T2 хочет `+7`, ожидаем итог `+12`):
1. T1: `begin`, `select death_year from alchemist where id = 1` → **1219**
2. T2: `begin`, `select death_year from alchemist where id = 1` → **1219**
3. T1: `update ... = 1224 where id = 1` (берёт row lock)
4. T2: `update ... = 1226 where id = 1` → ждёт row lock, удерживаемый T1
5. T1: `commit`
6. T2: блокировка снята, `update` выполняется, `commit`
7. Итог: `death_year = 1226`, разница `+7`. Прибавление `+5` от T1 потеряно.

Лечение, `select ... for update`:
1. T1: `begin`, `select ... for update` → **1219** (берёт блокировку)
2. T2: `begin`, `select ... for update` → ждёт
3. T1: `update ... = 1224`, `commit`
4. T2: блокировка снята, `select for update` возвращает уже **1224**, `update ... = 1231`, `commit`
5. Итог: `death_year = 1231`, разница `+12`.

Полный лог: [04_lost_update.log](results/04_lost_update.log).

```
--- read committed без блокировок ---
[T1] -> [(1219,)]
[T2] -> [(1219,)]
[T1] update alchemist set death_year = 1224 where id = 1
[T2] update alchemist set death_year = 1226 where id = 1
[--] t2 ожидает блокировку строки, удерживаемую t1
[T1] commit
[T2] commit
итог: death_year = 1226, разница 7 (ожидали +12, обновление t1 потеряно)

--- select for update ---
[T1] select death_year from alchemist where id = 1 for update
[T1] -> [(1219,)]
[T2] select death_year from alchemist where id = 1 for update
[--] t2 ждёт блокировку на select for update
[T1] update alchemist set death_year = 1224 where id = 1
[T1] commit
[T2] -> [(1224,)]
[T2] update alchemist set death_year = 1231 where id = 1
[T2] commit
итог: death_year = 1231, разница 12 (оба обновления применились)
```

**Как избежать.**
- Брать блокировку на чтении: `select ... for update`.
- Поднять уровень транзакции до `repeatable read`. Тогда вторая транзакция при `update` получит ошибку `could not serialize access due to concurrent update` и приложение должно повторить транзакцию.
- Делать атомарную модификацию одним выражением без `select`: `update alchemist set death_year = death_year + 5 where id = 1`.
