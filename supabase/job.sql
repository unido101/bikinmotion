-- =====================================================================
-- bikinmotion: antrian job render, kunci API terenkripsi (Vault), dan penyimpanan berkas
-- Jalankan di Supabase > SQL Editor SETELAH schema.sql. Aman dijalankan ulang.
--
-- Pembagian peran:
--   browser (anon/authenticated) : membuat job milik sendiri, membaca job sendiri, menyimpan/menghapus kunci sendiri
--   worker (service_role, server) : mengambil job, membaca kunci pemilik job, mengunggah hasil
-- Kunci API tidak pernah bisa dibaca kembali oleh browser; hanya worker lewat fungsi khusus.
-- =====================================================================

-- Vault menyimpan rahasia terenkripsi. Jika baris ini error, aktifkan dulu lewat Database > Extensions > Vault.
create extension if not exists supabase_vault;

-- ---------------------------------------------------------------- kunci API per pengguna
create table if not exists public.kunci_api (
  user_id     uuid not null references auth.users (id) on delete cascade,
  penyedia    text not null check (penyedia in ('gemini')),
  secret_id   uuid not null,                       -- rujukan ke vault.secrets; TIDAK terbaca oleh browser
  akhir       text not null,                       -- 4 karakter terakhir, hanya untuk ditampilkan
  diperbarui  timestamptz not null default now(),
  primary key (user_id, penyedia)
);

alter table public.kunci_api enable row level security;
revoke all on public.kunci_api from anon, authenticated;
grant select (user_id, penyedia, akhir, diperbarui) on public.kunci_api to authenticated;

drop policy if exists kunci_baca_sendiri on public.kunci_api;
create policy kunci_baca_sendiri on public.kunci_api
  for select to authenticated
  using (user_id = (select auth.uid()));

create or replace function public.simpan_kunci(p_penyedia text, p_nilai text)
returns text
language plpgsql
security definer
set search_path = public
as $$
declare
  uid uuid := (select auth.uid());
  n   text := btrim(coalesce(p_nilai, ''));
  sid uuid;
begin
  if uid is null then raise exception 'Belum masuk.'; end if;
  if not public.akses_aktif() then raise exception 'Akun belum aktif.'; end if;
  if p_penyedia is distinct from 'gemini' then raise exception 'Penyedia tidak dikenal.'; end if;
  if n !~ '^[A-Za-z0-9_.=+/-]{16,256}$' then raise exception 'Format kunci tidak valid. Salin ulang kunci dari Google AI Studio.'; end if;

  select secret_id into sid from public.kunci_api where user_id = uid and penyedia = p_penyedia;
  if sid is null then
    sid := vault.create_secret(n, 'kunci:' || uid::text || ':' || p_penyedia, 'kunci API milik pengguna');
    insert into public.kunci_api (user_id, penyedia, secret_id, akhir) values (uid, p_penyedia, sid, right(n, 4));
  else
    perform vault.update_secret(sid, n);
    update public.kunci_api set akhir = right(n, 4), diperbarui = now() where user_id = uid and penyedia = p_penyedia;
  end if;
  return right(n, 4);
end;
$$;

create or replace function public.hapus_kunci(p_penyedia text)
returns void
language plpgsql
security definer
set search_path = public
as $$
declare
  uid uuid := (select auth.uid());
  sid uuid;
begin
  if uid is null then raise exception 'Belum masuk.'; end if;
  select secret_id into sid from public.kunci_api where user_id = uid and penyedia = p_penyedia;
  if sid is not null then
    delete from vault.secrets where id = sid;
    delete from public.kunci_api where user_id = uid and penyedia = p_penyedia;
  end if;
end;
$$;

-- Hanya worker (service_role) yang boleh membaca kunci dalam bentuk asli.
create or replace function public.kunci_untuk_worker(p_user uuid, p_penyedia text)
returns text
language sql
stable
security definer
set search_path = public
as $$
  select ds.decrypted_secret
  from public.kunci_api k
  join vault.decrypted_secrets ds on ds.id = k.secret_id
  where k.user_id = p_user and k.penyedia = p_penyedia;
$$;

revoke all on function public.simpan_kunci(text, text)    from public, anon;
revoke all on function public.hapus_kunci(text)           from public, anon;
revoke all on function public.kunci_untuk_worker(uuid, text) from public, anon, authenticated;
grant execute on function public.simpan_kunci(text, text) to authenticated;
grant execute on function public.hapus_kunci(text)        to authenticated;
grant execute on function public.kunci_untuk_worker(uuid, text) to service_role;

-- ---------------------------------------------------------------- job render
create table if not exists public.job (
  id          uuid primary key default gen_random_uuid(),
  user_id     uuid not null default auth.uid() references auth.users (id) on delete cascade,
  status      text not null default 'antri' check (status in ('antri', 'berjalan', 'selesai', 'gagal', 'dibatalkan')),
  judul       text,
  style       text not null check (char_length(style) <= 40),
  naskah      jsonb not null,
  progres     int  not null default 0 check (progres between 0 and 100),
  tahap       text,
  pesan       text,
  hasil_path  text,
  kontak_path text,
  durasi      numeric,
  percobaan   int  not null default 0,
  worker      text,
  dibuat      timestamptz not null default now(),
  mulai       timestamptz,
  selesai     timestamptz,
  diperbarui  timestamptz not null default now()
);
create index if not exists job_antri_idx on public.job (dibuat) where status = 'antri';
create index if not exists job_user_idx  on public.job (user_id, dibuat desc);

alter table public.job enable row level security;
revoke all on public.job from anon, authenticated;
grant select on public.job to authenticated;
grant insert (judul, style, naskah) on public.job to authenticated;   -- user_id diisi otomatis dari sesi, tidak bisa dipalsukan
grant update (status) on public.job to authenticated;                 -- hanya untuk membatalkan (dibatasi kebijakan)

drop policy if exists job_baca_sendiri on public.job;
create policy job_baca_sendiri on public.job for select to authenticated
  using (user_id = (select auth.uid()));

drop policy if exists job_baca_admin on public.job;
create policy job_baca_admin on public.job for select to authenticated
  using (public.adalah_admin());

drop policy if exists job_buat_sendiri on public.job;
create policy job_buat_sendiri on public.job for insert to authenticated
  with check (user_id = (select auth.uid()) and public.akses_aktif());

drop policy if exists job_batal_sendiri on public.job;
create policy job_batal_sendiri on public.job for update to authenticated
  using      (user_id = (select auth.uid()) and status = 'antri')
  with check (user_id = (select auth.uid()) and status = 'dibatalkan');

-- Batas pemakaian per akun (ubah angkanya di sini sesuai paket langganan).
create or replace function public.batasi_job_baru()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
declare
  aktif int;
  harian int;
begin
  if jsonb_typeof(new.naskah) <> 'object' then raise exception 'Naskah tidak valid.'; end if;
  if pg_column_size(new.naskah) > 200000 then raise exception 'Naskah terlalu besar (maksimal 200 KB).'; end if;
  select count(*) into aktif  from public.job where user_id = new.user_id and status in ('antri', 'berjalan');
  if aktif >= 2 then raise exception 'Masih ada 2 video yang diproses. Tunggu salah satunya selesai.'; end if;
  select count(*) into harian from public.job where user_id = new.user_id and dibuat > now() - interval '24 hours';
  if harian >= 20 then raise exception 'Batas 20 video per 24 jam tercapai. Coba lagi besok.'; end if;
  new.judul := left(coalesce(new.judul, new.naskah ->> 'judul', ''), 120);
  return new;
end;
$$;

drop trigger if exists sebelum_job_baru on public.job;
create trigger sebelum_job_baru before insert on public.job
  for each row execute function public.batasi_job_baru();

-- ---------------------------------------------------------------- fungsi khusus worker (service_role)
create or replace function public.ambil_job_berikutnya(p_worker text)
returns setof public.job
language plpgsql
security definer
set search_path = public
as $$
begin
  return query
  update public.job j
     set status = 'berjalan', worker = left(p_worker, 60), mulai = now(), diperbarui = now(),
         progres = 0, tahap = 'Memulai', pesan = null, percobaan = j.percobaan + 1
   where j.id = (select id from public.job where status = 'antri' order by dibuat for update skip locked limit 1)
  returning j.*;
end;
$$;

-- Job yang 'berjalan' tapi tidak bergerak (worker mati): diulang sekali, setelah itu dinyatakan gagal.
create or replace function public.pulihkan_job_macet(p_menit int default 15)
returns int
language plpgsql
security definer
set search_path = public
as $$
declare n int;
begin
  update public.job
     set status = case when percobaan < 2 then 'antri' else 'gagal' end,
         pesan  = case when percobaan < 2 then 'Diulang otomatis karena prosesnya terhenti.'
                       else 'Proses terhenti berulang kali. Coba buat ulang atau hubungi admin.' end,
         tahap = null, worker = null, progres = 0, diperbarui = now(),
         selesai = case when percobaan < 2 then null else now() end
   where status = 'berjalan' and diperbarui < now() - make_interval(mins => p_menit);
  get diagnostics n = row_count;
  return n;
end;
$$;

create or replace function public.daftar_job_kedaluwarsa(p_hari int default 7)
returns table (id uuid, user_id uuid, hasil_path text, kontak_path text)
language sql
stable
security definer
set search_path = public
as $$
  select j.id, j.user_id, j.hasil_path, j.kontak_path
  from public.job j
  where j.status in ('selesai', 'gagal')
    and j.selesai < now() - make_interval(days => p_hari)
    and (j.hasil_path is not null or j.kontak_path is not null)
  limit 200;
$$;

revoke all on function public.ambil_job_berikutnya(text)   from public, anon, authenticated;
revoke all on function public.pulihkan_job_macet(int)      from public, anon, authenticated;
revoke all on function public.daftar_job_kedaluwarsa(int)  from public, anon, authenticated;
grant execute on function public.ambil_job_berikutnya(text)  to service_role;
grant execute on function public.pulihkan_job_macet(int)     to service_role;
grant execute on function public.daftar_job_kedaluwarsa(int) to service_role;

-- ---------------------------------------------------------------- penyimpanan berkas
-- unggahan: gambar milik pengguna (folder = id pengguna). hasil: video dan lembar kontak (hanya diunggah worker).
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('unggahan', 'unggahan', false, 8 * 1024 * 1024, array['image/png', 'image/jpeg', 'image/webp'])
on conflict (id) do update set public = false, file_size_limit = excluded.file_size_limit, allowed_mime_types = excluded.allowed_mime_types;

insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('hasil', 'hasil', false, 200 * 1024 * 1024, array['video/mp4', 'image/png'])
on conflict (id) do update set public = false, file_size_limit = excluded.file_size_limit, allowed_mime_types = excluded.allowed_mime_types;

drop policy if exists unggahan_baca_sendiri on storage.objects;
create policy unggahan_baca_sendiri on storage.objects for select to authenticated
  using (bucket_id = 'unggahan' and (storage.foldername(name))[1] = (select auth.uid())::text);

drop policy if exists unggahan_tulis_sendiri on storage.objects;
create policy unggahan_tulis_sendiri on storage.objects for insert to authenticated
  with check (bucket_id = 'unggahan' and (storage.foldername(name))[1] = (select auth.uid())::text and public.akses_aktif());

drop policy if exists unggahan_hapus_sendiri on storage.objects;
create policy unggahan_hapus_sendiri on storage.objects for delete to authenticated
  using (bucket_id = 'unggahan' and (storage.foldername(name))[1] = (select auth.uid())::text);

drop policy if exists hasil_baca_sendiri on storage.objects;
create policy hasil_baca_sendiri on storage.objects for select to authenticated
  using (bucket_id = 'hasil' and (storage.foldername(name))[1] = (select auth.uid())::text);
-- Tidak ada kebijakan tulis untuk bucket 'hasil': hanya worker (service_role, melewati RLS) yang mengunggah.
