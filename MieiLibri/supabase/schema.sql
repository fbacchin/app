-- Schema del database Supabase per MieiLibri.
-- Tabella dei libri letti, una riga per utente e per libro,
-- protetta da Row Level Security: ogni utente vede solo i suoi libri.

create extension if not exists moddatetime schema extensions;

create table public.books (
  id text not null,
  user_id uuid not null default auth.uid() references auth.users (id) on delete cascade,
  title text not null,
  authors text[] not null default '{}',
  publisher text,
  published_year text,
  isbn text,
  page_count integer,
  cover_url text,
  date_read timestamptz not null default now(),
  rating integer not null default 0 check (rating between 0 and 5),
  notes text not null default '',
  updated_at timestamptz not null default now(),
  primary key (user_id, id)
);

comment on table public.books is 'Libri letti degli utenti dell''app MieiLibri';

create index books_user_date_read on public.books (user_id, date_read desc);

alter table public.books enable row level security;

create policy "select own books" on public.books
  for select to authenticated
  using ((select auth.uid()) = user_id);

create policy "insert own books" on public.books
  for insert to authenticated
  with check ((select auth.uid()) = user_id);

create policy "update own books" on public.books
  for update to authenticated
  using ((select auth.uid()) = user_id)
  with check ((select auth.uid()) = user_id);

create policy "delete own books" on public.books
  for delete to authenticated
  using ((select auth.uid()) = user_id);

create trigger books_updated_at
  before update on public.books
  for each row execute function extensions.moddatetime (updated_at);
