-- =====================================================================
-- Uji antrian job, kunci terenkripsi, dan penyimpanan. Jalankan SELURUH berkas ini di SQL Editor
-- SETELAH schema.sql dan job.sql. Satu transaksi yang di-ROLLBACK: tidak meninggalkan data.
-- Hasil yang diharapkan: NOTICE "SEMUA UJI LOLOS". Jika ada yang gagal muncul galat "GAGAL: ...";
-- jika galatnya dari INSERT ke auth.users atau set role, itu masalah skrip uji untuk versi Supabase-mu: kirim pesannya.
-- =====================================================================
begin;

do $uji$
declare
  adm uuid := gen_random_uuid(); u1 uuid := gen_random_uuid(); u2 uuid := gen_random_uuid(); u3 uuid := gen_random_uuid();
  n int; t text; j1 uuid; j2 uuid; kunci text;
begin
  insert into auth.users (id, email) values
    (adm, 'j-admin@contoh.test'), (u1, 'j-u1@contoh.test'), (u2, 'j-u2@contoh.test'), (u3, 'j-u3@contoh.test');
  update public.profil set peran = 'admin', status = 'aktif', aktif_sampai = null where id = adm;
  update public.profil set status = 'aktif', aktif_sampai = now() + interval '30 days' where id in (u1, u2);   -- u3 tetap 'menunggu'

  ------------------------------------------------------------------ job: u1
  perform set_config('request.jwt.claim.sub', u1::text, true);
  perform set_config('request.jwt.claims', json_build_object('sub', u1, 'role', 'authenticated')::text, true);
  set local role authenticated;

  insert into public.job (style, naskah) values ('kartun-hangat', '{"judul":"Satu","bagian":[]}'::jsonb) returning id into j1;
  select count(*) into n from public.job;
  if n <> 1 then raise exception 'GAGAL: u1 harus melihat 1 job miliknya, terlihat %', n; end if;
  select judul into t from public.job where id = j1;
  if t is distinct from 'Satu' then raise exception 'GAGAL: judul harus diambil dari naskah, bukan %', t; end if;

  begin
    insert into public.job (user_id, style, naskah) values (u2, 'kartun-hangat', '{}'::jsonb);
    raise exception 'GAGAL: u1 berhasil membuat job atas nama user lain';
  exception when insufficient_privilege then null;
  end;

  begin
    update public.job set progres = 100 where id = j1;
    raise exception 'GAGAL: u1 berhasil mengubah kolom progres';
  exception when insufficient_privilege then null;
  end;

  begin
    update public.job set status = 'selesai' where id = j1;
    raise exception 'GAGAL: u1 berhasil menandai job selesai sendiri';
  exception when insufficient_privilege then null;
  end;

  begin
    insert into public.job (style, naskah) values ('kartun-hangat', '[1,2]'::jsonb);
    raise exception 'GAGAL: naskah bukan objek harus ditolak';
  exception when raise_exception then
    if sqlerrm like 'GAGAL%' then raise; end if;
  end;

  insert into public.job (style, naskah) values ('kartun-hangat', '{"judul":"Dua"}'::jsonb);
  begin
    insert into public.job (style, naskah) values ('kartun-hangat', '{"judul":"Tiga"}'::jsonb);
    raise exception 'GAGAL: job aktif ketiga harus ditolak';
  exception when raise_exception then
    if sqlerrm like 'GAGAL%' then raise; end if;
    if sqlerrm not like '%Masih ada 2 video%' then raise exception 'GAGAL: pesan batas salah: %', sqlerrm; end if;
  end;

  update public.job set status = 'dibatalkan' where id = j1;
  get diagnostics n = row_count;
  if n <> 1 then raise exception 'GAGAL: u1 harus bisa membatalkan job antri miliknya'; end if;
  update public.job set status = 'dibatalkan' where id = j1;
  get diagnostics n = row_count;
  if n <> 0 then raise exception 'GAGAL: job yang sudah dibatalkan tidak boleh diubah lagi'; end if;
  reset role;

  ------------------------------------------------------------------ job: u2 tidak boleh menyentuh milik u1, u3 (menunggu) tidak boleh membuat
  perform set_config('request.jwt.claim.sub', u2::text, true);
  perform set_config('request.jwt.claims', json_build_object('sub', u2, 'role', 'authenticated')::text, true);
  set local role authenticated;
  select count(*) into n from public.job;
  if n <> 0 then raise exception 'GAGAL: u2 tidak boleh melihat job user lain, terlihat %', n; end if;
  update public.job set status = 'dibatalkan' where user_id = u1;
  get diagnostics n = row_count;
  if n <> 0 then raise exception 'GAGAL: u2 berhasil membatalkan job user lain'; end if;
  reset role;

  perform set_config('request.jwt.claim.sub', u3::text, true);
  perform set_config('request.jwt.claims', json_build_object('sub', u3, 'role', 'authenticated')::text, true);
  set local role authenticated;
  begin
    insert into public.job (style, naskah) values ('kartun-hangat', '{}'::jsonb);
    raise exception 'GAGAL: akun menunggu berhasil membuat job';
  exception when insufficient_privilege then null;
  end;
  begin
    perform public.simpan_kunci('gemini', 'AIzaSyAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA');
    raise exception 'GAGAL: akun menunggu berhasil menyimpan kunci';
  exception when raise_exception then
    if sqlerrm like 'GAGAL%' then raise; end if;
    if sqlerrm not like '%belum aktif%' then raise exception 'GAGAL: pesan salah: %', sqlerrm; end if;
  end;
  reset role;

  ------------------------------------------------------------------ kunci API
  perform set_config('request.jwt.claim.sub', u1::text, true);
  perform set_config('request.jwt.claims', json_build_object('sub', u1, 'role', 'authenticated')::text, true);
  set local role authenticated;

  begin
    perform public.simpan_kunci('gemini', 'pendek');
    raise exception 'GAGAL: kunci berformat salah harus ditolak';
  exception when raise_exception then
    if sqlerrm like 'GAGAL%' then raise; end if;
  end;

  t := public.simpan_kunci('gemini', 'AIzaSyKUNCI-U1-RAHASIA-0000-abcdWXYZ');
  if t <> 'WXYZ' then raise exception 'GAGAL: simpan_kunci harus mengembalikan 4 karakter terakhir, dapat %', t; end if;

  select akhir into t from public.kunci_api where penyedia = 'gemini';
  if t is distinct from 'WXYZ' then raise exception 'GAGAL: u1 harus membaca akhir kuncinya'; end if;

  begin
    perform secret_id from public.kunci_api;
    raise exception 'GAGAL: browser berhasil membaca kolom secret_id';
  exception when insufficient_privilege then null;
  end;

  begin
    perform public.kunci_untuk_worker(u1, 'gemini');
    raise exception 'GAGAL: user biasa berhasil memanggil kunci_untuk_worker';
  exception when insufficient_privilege then null;
  end;

  begin
    perform 1 from vault.decrypted_secrets;
    raise exception 'GAGAL: user biasa berhasil membaca vault.decrypted_secrets';
  exception when insufficient_privilege or invalid_schema_name then null;
  end;
  reset role;

  perform set_config('request.jwt.claim.sub', u2::text, true);
  perform set_config('request.jwt.claims', json_build_object('sub', u2, 'role', 'authenticated')::text, true);
  set local role authenticated;
  select count(*) into n from public.kunci_api;
  if n <> 0 then raise exception 'GAGAL: u2 tidak boleh melihat kunci u1'; end if;
  reset role;

  -- worker (service_role) membaca kunci asli; kunci diperbarui terbaca versi baru
  set local role service_role;
  kunci := public.kunci_untuk_worker(u1, 'gemini');
  if kunci is distinct from 'AIzaSyKUNCI-U1-RAHASIA-0000-abcdWXYZ' then raise exception 'GAGAL: worker harus membaca kunci asli, dapat %', kunci; end if;
  if public.kunci_untuk_worker(u2, 'gemini') is not null then raise exception 'GAGAL: kunci u2 tidak ada, harus null'; end if;
  reset role;

  perform set_config('request.jwt.claim.sub', u1::text, true);
  perform set_config('request.jwt.claims', json_build_object('sub', u1, 'role', 'authenticated')::text, true);
  set local role authenticated;
  perform public.simpan_kunci('gemini', 'AIzaSyKUNCI-U1-BARU-1111-abcdQRST');
  reset role;
  set local role service_role;
  if public.kunci_untuk_worker(u1, 'gemini') is distinct from 'AIzaSyKUNCI-U1-BARU-1111-abcdQRST' then raise exception 'GAGAL: kunci baru harus terbaca worker'; end if;
  reset role;

  select count(*) into n from vault.secrets where name = 'kunci:' || u1::text || ':gemini';
  if n <> 1 then raise exception 'GAGAL: harus ada tepat 1 rahasia di vault untuk u1, ada %', n; end if;

  perform set_config('request.jwt.claim.sub', u1::text, true);
  perform set_config('request.jwt.claims', json_build_object('sub', u1, 'role', 'authenticated')::text, true);
  set local role authenticated;
  perform public.hapus_kunci('gemini');
  reset role;
  select count(*) into n from vault.secrets where name = 'kunci:' || u1::text || ':gemini';
  if n <> 0 then raise exception 'GAGAL: hapus_kunci harus menghapus rahasia dari vault'; end if;

  ------------------------------------------------------------------ antrian (worker)
  update public.job set status = 'antri' where user_id = u1;                              -- sebagai pemilik tabel: siapkan job antri

  set local role service_role;
  select id into j2 from public.ambil_job_berikutnya('w-uji') limit 1;
  if j2 is null then raise exception 'GAGAL: worker harus bisa mengambil job antri'; end if;
  select percobaan into n from public.job where id = j2;
  if n <> 1 then raise exception 'GAGAL: percobaan harus 1 setelah diambil, dapat %', n; end if;
  reset role;

  update public.job set diperbarui = now() - interval '1 hour' where id = j2;             -- simulasi worker mati
  set local role service_role;
  if public.pulihkan_job_macet(15) < 1 then raise exception 'GAGAL: job macet harus dipulihkan'; end if;
  reset role;
  select status into t from public.job where id = j2;
  if t <> 'antri' then raise exception 'GAGAL: job macet percobaan pertama harus kembali antri, status %', t; end if;

  begin
    set local role authenticated;
    perform * from public.ambil_job_berikutnya('x');
    raise exception 'GAGAL: user biasa berhasil memanggil ambil_job_berikutnya';
  exception when insufficient_privilege then null;
  end;
  reset role;

  ------------------------------------------------------------------ penyimpanan
  select file_size_limit into n from storage.buckets where id = 'unggahan';
  if n is distinct from 8388608 then raise exception 'GAGAL: batas ukuran bucket unggahan harus 8 MB'; end if;
  select count(*) into n from storage.buckets where id in ('unggahan', 'hasil') and public = false;
  if n <> 2 then raise exception 'GAGAL: kedua bucket harus privat'; end if;

  perform set_config('request.jwt.claim.sub', u1::text, true);
  perform set_config('request.jwt.claims', json_build_object('sub', u1, 'role', 'authenticated')::text, true);
  set local role authenticated;
  insert into storage.objects (bucket_id, name) values ('unggahan', u1::text || '/foto.png');
  begin
    insert into storage.objects (bucket_id, name) values ('unggahan', u2::text || '/foto.png');
    raise exception 'GAGAL: u1 berhasil mengunggah ke folder u2';
  exception when insufficient_privilege then null;
  end;
  begin
    insert into storage.objects (bucket_id, name) values ('hasil', u1::text || '/palsu.mp4');
    raise exception 'GAGAL: user berhasil menulis ke bucket hasil';
  exception when insufficient_privilege then null;
  end;
  reset role;

  perform set_config('request.jwt.claim.sub', u2::text, true);
  perform set_config('request.jwt.claims', json_build_object('sub', u2, 'role', 'authenticated')::text, true);
  set local role authenticated;
  select count(*) into n from storage.objects where bucket_id = 'unggahan';
  if n <> 0 then raise exception 'GAGAL: u2 tidak boleh melihat gambar u1, terlihat %', n; end if;
  reset role;

  raise notice 'SEMUA UJI LOLOS';
end;
$uji$;

rollback;
