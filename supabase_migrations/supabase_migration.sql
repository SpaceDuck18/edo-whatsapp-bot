-- supabase_migration.sql
create table if not exists shop_whatsapp_mappings (
  id uuid primary key default gen_random_uuid(),
  shop_id uuid,
  seller_user_id uuid references users(id),
  whatsapp_phone text not null,
  whatsapp_phone_id text,
  created_at timestamptz default now()
);

create table if not exists orders (
  id uuid primary key default gen_random_uuid(),
  item_id uuid references marketplace_items(id),
  buyer_user_id uuid references users(id),
  seller_user_id uuid references users(id),
  quantity int default 1,
  price numeric(10,2),
  status text default 'created',
  whatsapp_thread_id text,
  created_at timestamptz default now()
);

create table if not exists whatsapp_messages (
  id uuid primary key default gen_random_uuid(),
  direction text,
  whatsapp_from text,
  whatsapp_to text,
  payload jsonb,
  user_id uuid references users(id),
  shop_id uuid,
  order_id uuid references orders(id),
  created_at timestamptz default now()
);