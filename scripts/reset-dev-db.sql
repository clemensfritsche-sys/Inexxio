-- ►►► Die dev-Datenbank leeren, damit sie neu aus den Migrationen entsteht. ◄◄◄
--
-- Wofür: dev stand auf Migration 077, alles danach hatten nur die Start-Netze nachgebaut
-- (docs/history/2026-10-28-dokumente.md). Eine Datenbank, die nicht aus den Migrationen kommt,
-- ist nicht die, die prod bekommt. Nach diesem Lauf baut der nächste Start `alembic upgrade
-- head` von 001 an – genau wie die CI.
--
-- Was es tut: löscht in `public` alle Tabellen, Sequenzen, eigenen Funktionen und Typen.
-- Der Benutzer, seine Rechte und Erweiterungen bleiben. **Alle Daten sind danach weg** –
-- vorher eine Sicherung anlegen (Cloud SQL → Sicherungen).
--
-- Wo: Cloud SQL Studio (Cloud Console → SQL → inexxio-dev-db → Cloud SQL Studio), angemeldet
-- an der Datenbank `inexxio_dev`. Auf jeder anderen Datenbank bricht es ab.
DO $$
DECLARE r record;
BEGIN
  IF current_database() <> 'inexxio_dev' THEN
    RAISE EXCEPTION 'Abbruch: das ist %, nicht inexxio_dev – dieses Skript leert nur dev.', current_database();
  END IF;
  FOR r IN SELECT tablename FROM pg_tables WHERE schemaname = 'public' LOOP
    EXECUTE format('DROP TABLE IF EXISTS public.%I CASCADE', r.tablename);
  END LOOP;
  FOR r IN SELECT sequence_name FROM information_schema.sequences WHERE sequence_schema = 'public' LOOP
    EXECUTE format('DROP SEQUENCE IF EXISTS public.%I CASCADE', r.sequence_name);
  END LOOP;
  FOR r IN SELECT p.oid::regprocedure AS fn FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
           WHERE n.nspname = 'public' AND p.prokind IN ('f', 'p')
             AND NOT EXISTS (SELECT 1 FROM pg_depend d WHERE d.objid = p.oid AND d.deptype = 'e') LOOP
    EXECUTE format('DROP ROUTINE IF EXISTS %s CASCADE', r.fn);
  END LOOP;
  FOR r IN SELECT t.typname FROM pg_type t JOIN pg_namespace n ON n.oid = t.typnamespace
           WHERE n.nspname = 'public' AND t.typtype IN ('e', 'd', 'c')
             AND NOT EXISTS (SELECT 1 FROM pg_class c WHERE c.oid = t.typrelid AND c.relkind <> 'c')
             AND NOT EXISTS (SELECT 1 FROM pg_depend d WHERE d.objid = t.oid AND d.deptype = 'e') LOOP
    EXECUTE format('DROP TYPE IF EXISTS public.%I CASCADE', r.typname);
  END LOOP;
  RAISE NOTICE 'inexxio_dev ist leer – der nächste Start baut sie aus den Migrationen.';
END $$;
