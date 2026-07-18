-- 0010_ai_brief_images_bucket.sql
-- AIVIZENS 简报头图公开桶：每天把 digest 选中的头图上传到此桶，邮件热链。
-- 独立于 NEV。幂等：可重复执行。

-- 公开可读桶（存 digest 头图，路径 ai/<date>/<module>-<hash>.png）
insert into storage.buckets (id, name, public)
values ('ai-brief-images', 'ai-brief-images', true)
on conflict (id) do update set public = true;

-- 公开读策略（匿名可 GET 该桶对象；写入走 service-role 绕过 RLS）
do $$
begin
  if not exists (
    select 1 from pg_policies
    where schemaname = 'storage' and tablename = 'objects'
      and policyname = 'ai_brief_images_public_read'
  ) then
    create policy ai_brief_images_public_read
      on storage.objects for select
      to public
      using (bucket_id = 'ai-brief-images');
  end if;
end $$;
