-- =====================================================================
-- Uji aturan akses (RLS). Jalankan SELURUH berkas ini di Supabase > SQL Editor SETELAH schema.sql.
-- Semuanya berada dalam satu transaksi yang di-ROLLBACK, jadi tidak meninggalkan data.
-- Hasil yang diharapkan: pesan NOTICE "SEMUA UJI LOLOS". Jika ada yang gagal, muncul galat
-- bertuliskan GAGAL: ... (kirim teksnya ke pembuat kode). Jika INSERT ke auth.users ditolak oleh versi Supabase-mu,
-- itu masalah skrip uji, bukan skema: kirim pesannya untuk disesuaikan.
-- =====================================================================
begin;

do $uji$
declare
  admin_id uuid := gen_random_uuid();
  user_id  uuid := gen_random_uuid();
  user2_id uuid := gen_random_uuid();
  n int;
  sts text;
begin
  -- siapkan tiga akun lewat tabel auth (trigger membuat profil 'menunggu')
  insert into auth.users (id, email) values (admin_id, 'uji-admin@contoh.test'), (user_id, 'uji-user@contoh.test'), (user2_id, 'uji-user2@contoh.test');
  update public.profil set peran = 'admin', status = 'aktif', aktif_sampai = null where id = admin_id;   -- sebagai pemilik tabel (SQL Editor)

  select status into sts from public.profil where id = user_id;
  if sts is distinct from 'menunggu' then raise exception 'GAGAL: akun baru harus berstatus menunggu, bukan %', sts; end if;

  ------------------------------------------------------------------ sebagai user biasa
  perform set_config('request.jwt.claim.sub', user_id::text, true);
  perform set_config('request.jwt.claims', json_build_object('sub', user_id, 'role', 'authenticated')::text, true);
  set local role authenticated;

  select count(*) into n from public.profil;
  if n <> 1 then raise exception 'GAGAL: user biasa hanya boleh melihat 1 profil (dirinya), terlihat %', n; end if;

  update public.profil set status = 'aktif' where id = user_id;
  get diagnostics n = row_count;
  if n <> 0 then raise exception 'GAGAL: user biasa tidak boleh mengaktifkan akunnya sendiri'; end if;

  begin
    update public.profil set peran = 'admin' where id = user_id;
    raise exception 'GAGAL: user biasa berhasil mengubah kolom peran';
  exception when insufficient_privilege then null;   -- diharapkan: ditolak
  end;

  begin
    insert into public.profil (id, email) values (gen_random_uuid(), 'palsu@contoh.test');
    raise exception 'GAGAL: user biasa berhasil menyisipkan profil';
  exception when insufficient_privilege then null;
  end;

  begin
    delete from public.profil where id = user2_id;
    get diagnostics n = row_count;
    if n <> 0 then raise exception 'GAGAL: user biasa berhasil menghapus profil'; end if;
  exception when insufficient_privilege then null;
  end;

  select count(*) into n from public.audit;
  if n <> 0 then raise exception 'GAGAL: user biasa tidak boleh membaca audit'; end if;

  if public.adalah_admin() then raise exception 'GAGAL: adalah_admin() true untuk user biasa'; end if;
  if public.akses_aktif()  then raise exception 'GAGAL: akses_aktif() true untuk akun yang masih menunggu'; end if;

  reset role;

  ------------------------------------------------------------------ anon (tanpa login)
  set local role anon;
  begin
    perform 1 from public.profil;
    raise exception 'GAGAL: anon bisa membaca profil';
  exception when insufficient_privilege then null;
  end;
  reset role;

  ------------------------------------------------------------------ sebagai admin
  perform set_config('request.jwt.claim.sub', admin_id::text, true);
  perform set_config('request.jwt.claims', json_build_object('sub', admin_id, 'role', 'authenticated')::text, true);
  set local role authenticated;

  if not public.adalah_admin() then raise exception 'GAGAL: adalah_admin() harus true untuk admin aktif'; end if;

  select count(*) into n from public.profil where id in (admin_id, user_id, user2_id);
  if n <> 3 then raise exception 'GAGAL: admin harus melihat semua profil, terlihat %', n; end if;

  update public.profil set status = 'aktif', aktif_sampai = now() + interval '30 days' where id = user_id;
  get diagnostics n = row_count;
  if n <> 1 then raise exception 'GAGAL: admin harus bisa mengaktifkan user'; end if;

  update public.profil set status = 'ditangguhkan' where id = admin_id;
  get diagnostics n = row_count;
  if n <> 0 then raise exception 'GAGAL: admin tidak boleh mengubah akunnya sendiri'; end if;

  begin
    update public.profil set peran = 'admin' where id = user2_id;
    raise exception 'GAGAL: admin berhasil mengubah kolom peran lewat API';
  exception when insufficient_privilege then null;
  end;

  select count(*) into n from public.audit where target = user_id and aksi = 'ubah_profil' and oleh = admin_id;
  if n <> 1 then raise exception 'GAGAL: audit harus mencatat 1 perubahan oleh admin, tercatat %', n; end if;

  reset role;

  ------------------------------------------------------------------ masa aktif
  perform set_config('request.jwt.claim.sub', user_id::text, true);
  perform set_config('request.jwt.claims', json_build_object('sub', user_id, 'role', 'authenticated')::text, true);
  set local role authenticated;
  if not public.akses_aktif() then raise exception 'GAGAL: akses_aktif() harus true setelah diaktifkan'; end if;
  reset role;

  update public.profil set aktif_sampai = now() - interval '1 day' where id = user_id;   -- sebagai pemilik: simulasi kedaluwarsa
  set local role authenticated;
  if public.akses_aktif() then raise exception 'GAGAL: akses_aktif() harus false setelah kedaluwarsa'; end if;
  reset role;

  raise notice 'SEMUA UJI LOLOS';
end;
$uji$;

rollback;
