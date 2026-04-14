create table if not exists customers (
    customer_id serial primary key,
    first_name varchar(100) not null,
    last_name varchar(100) not null,
    email varchar(255) not null unique
);

create table if not exists products (
    product_id serial primary key,
    product_name varchar(255) not null,
    price numeric(10, 2) not null check (price >= 0)
);

create table if not exists orders (
    order_id serial primary key,
    customer_id int not null references customers(customer_id),
    order_date timestamp not null default now(),
    total_amount numeric(10, 2) not null default 0
);

create table if not exists order_items (
    order_item_id serial primary key,
    order_id int not null references orders(order_id),
    product_id int not null references products(product_id),
    quantity int not null check (quantity > 0),
    subtotal numeric(10, 2) not null check (subtotal >= 0)
);

insert into customers (first_name, last_name, email) values
    ('oleg', 'sandrs', 'olegsandr@gmail.com'),
    ('grisha', 'kirov', 'kirovgv@mail.ru');

insert into products (product_name, price) values
    ('laptop', 75000.00),
    ('mouse', 1500.00),
    ('keyboard', 3000.00),
    ('monitor', 25000.00),
    ('headphones', 5500.00);

create or replace function place_order(
    p_customer_id int,
    p_items jsonb
) returns int as $$
declare
    new_order_id int;
begin
    with items as (
        select 
            (item->>'product_id')::int as product_id,
            (item->>'quantity')::int as quantity
        from jsonb_array_elements(p_items) as item
    ),
    priced as (
        select 
            i.product_id,
            i.quantity,
            i.quantity * p.price as subtotal
        from items i
        join products p using (product_id)
    ),
    new_order as (
        insert into orders (customer_id, total_amount)
        select p_customer_id, coalesce(sum(subtotal), 0)
        from priced
        returning order_id
    ),
    inserted_items as (
        insert into order_items (order_id, product_id, quantity, subtotal)
        select o.order_id, p.product_id, p.quantity, p.subtotal
        from priced p
        cross join new_order o
        returning order_id
    )
    select order_id into new_order_id from new_order;

    return new_order_id;
end;
$$ language plpgsql;

create or replace function update_customer_email(
    p_customer_id int,
    p_new_email varchar
) returns void as $$
begin
    update customers set email = p_new_email where customer_id = p_customer_id;

    if not found then
        raise exception 'customer with id % not found', p_customer_id;
    end if;
end;
$$ language plpgsql;

create or replace function add_product(
    p_product_name varchar,
    p_price numeric
) returns int as $$
declare
    new_product_id int;
begin
    insert into products (product_name, price)
    values (p_product_name, p_price)
    returning product_id into new_product_id;

    return new_product_id;
end;
$$ language plpgsql;
