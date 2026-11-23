-- =====================================================================
-- bikinmotion: akun, persetujuan admin, dan masa langganan (Supabase)
-- Jalankan sekali di Supabase > SQL Editor. Aman dijalankan ulang.
--
-- Prinsip: keamanan ada di basis data (Row Level Security), bukan di halaman web.
-- Kunci publik (anon/publishable) memang terlihat di browser; yang melindungi data
-- hanyalah aturan di bawah ini.
-- =====================================================================

-- ---------- tabel profil: satu baris per akun ----------
create table if not exists public.profil (
  id           uuid primary key references auth.users (id) on delete cascade,
  email        text not null,
  status       text not null default 'menunggu' check (status in ('menunggu', 'aktif', 'ditangguhkan')),
  peran        text not null default 'user' check (peran in ('user', 'admin')),
  aktif_sampai timestamptz,                       -- kosong = tanpa batas waktu (dipakai untuk admin)
  dibuat       timestamptz not null default now(),
  diperbarui   timestamptz not null default now()
);

-- ---------- tabel audit: siapa mengubah apa ----------
create table if not exists public.audit (
  id      bigint generated always as identity primary key,
  waktu   timestamptz not null default now(),
  oleh    uuid,                                   -- kosong = dijalankan dari SQL Editor / sistem
  target  uuid not null,
  aksi    text not null,
  sebelum jsonb,
  sesudah jsonb
);

-- ---------- akun baru otomatis berstatus 'menunggu' ----------
create or replace function public.buat_profil_baru()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  insert into public.profil (id, email) values (new.id, coalesce(new.email, ''));
  return new;
end;
$$;

drop trigger if exists saat_user_baru on auth.users;
create trigger saat_user_baru
  after insert on auth.users
  for each row execute function public.buat_profil_baru();

-- ---------- fungsi bantu ----------
create or replace function public.adalah_admin()
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select exists (
    select 1 from public.profil p
    where p.id = (select auth.uid()) and p.peran = 'admin' and p.status = 'aktif'
  );
$$;

-- Dipakai tabel-tabel berikutnya (job, kunci API) untuk menolak akun yang belum atau tidak lagi berlangganan.
create or replace function public.akses_aktif()
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select exists (
    select 1 from public.profil p
    where p.id = (select auth.uid())
      and p.status = 'aktif'
      and (p.aktif_sampai is null or p.aktif_sampai > now())
  );
$$;

revoke all on function public.adalah_admin() from public, anon;
revoke all on function public.akses_aktif()  from public, anon;
grant execute on function public.adalah_admin() to authenticated;
grant execute on function public.akses_aktif()  to authenticated;

-- ---------- catat perubahan status/masa aktif + cap waktu ----------
create or replace function public.catat_perubahan_profil()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  new.diperbarui := now();
  if old.status is distinct from new.status or old.aktif_sampai is distinct from new.aktif_sampai then
    insert into public.audit (oleh, target, aksi, sebelum, sesudah)
    values (
      (select auth.uid()), new.id, 'ubah_profil',
      jsonb_build_object('status', old.status, 'aktif_sampai', old.aktif_sampai),
      jsonb_build_object('status', new.status, 'aktif_sampai', new.aktif_sampai)
    );
  end if;
  return new;
end;
$$;

drop trigger if exists sebelum_ubah_profil on public.profil;
create trigger sebelum_ubah_profil
  before update on public.profil
  for each row execute function public.catat_perubahan_profil();

-- ---------- hak akses tingkat tabel (dievaluasi SEBELUM aturan baris) ----------
revoke all on public.profil from anon, authenticated;
revoke all on public.audit  from anon, authenticated;
grant select on public.profil to authenticated;
grant update (status, aktif_sampai) on public.profil to authenticated;   -- peran, email, id TIDAK bisa diubah lewat API
grant select on public.audit to authenticated;

-- ---------- Row Level Security ----------
alter table public.profil enable row level security;
alter table public.audit  enable row level security;

drop policy if exists profil_baca_sendiri on public.profil;
create policy profil_baca_sendiri on public.profil
  for select to authenticated
  using (id = (select auth.uid()));

drop policy if exists profil_baca_admin on public.profil;
create policy profil_baca_admin on public.profil
  for select to authenticated
  using (public.adalah_admin());

-- Hanya admin yang boleh mengubah status/masa aktif, dan tidak boleh pada akunnya sendiri (cegah terkunci).
drop policy if exists profil_ubah_admin on public.profil;
create policy profil_ubah_admin on public.profil
  for update to authenticated
  using      (public.adalah_admin() and id <> (select auth.uid()))
  with check (public.adalah_admin() and id <> (select auth.uid()));

drop policy if exists audit_baca_admin on public.audit;
create policy audit_baca_admin on public.audit
  for select to authenticated
  using (public.adalah_admin());

-- Tidak ada kebijakan insert/delete untuk pengguna: baris profil hanya dibuat oleh trigger di atas.

-- =====================================================================
-- LANGKAH MANUAL: jadikan akunmu admin (sekali saja, setelah kamu mendaftar lewat halaman masuk).
-- Jalankan di SQL Editor dengan emailmu:
--
--   update public.profil
--      set peran = 'admin', status = 'aktif', aktif_sampai = null
--    where email = 'emailkamu@contoh.com';
-- =====================================================================
