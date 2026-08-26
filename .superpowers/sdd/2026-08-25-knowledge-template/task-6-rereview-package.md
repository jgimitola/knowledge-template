# Task 6 fix-round 2 scoped diff

FIX_BASE: c4cc611
HEAD: b3f8401

## Commits
```
b3f8401 fix: reject a glob template that cannot substitute its segment
```

## Stat
```
 src/knowledge/config.py | 16 ++++++++++++++--
 tests/test_config.py    | 26 ++++++++++++++++++++++++++
 2 files changed, 40 insertions(+), 2 deletions(-)
```

## Full diff (-U15)
```diff
diff --git a/src/knowledge/config.py b/src/knowledge/config.py
index 09c9b60..ed797b3 100644
--- a/src/knowledge/config.py
+++ b/src/knowledge/config.py
@@ -136,35 +136,47 @@ def _publish(data: dict) -> Publish:
             nested_under=dict(bar.get("nested_under", {})),
             header_before=dict(bar.get("header_before", {})),
             labels=dict(bar.get("labels", {})),
         ),
     )
 
 
 def _dependencies(data: dict) -> Dependencies:
     table = data.get("dependencies", {})
     dynamic_segment = _clean(table.get("dynamic_segment")) or "{...}"
     if "..." not in dynamic_segment:
         raise ConfigError(
             f"knowledge.toml: dependencies.dynamic_segment is {dynamic_segment!r};"
             " it must contain '...' to mark where the segment name goes (e.g. '{...}', '<...>')"
         )
+    route_glob = _clean(table.get("route_glob"))
+    if route_glob and "{segments}" not in route_glob:
+        raise ConfigError(
+            f"knowledge.toml: dependencies.route_glob is {route_glob!r};"
+            " it must contain '{segments}' to mark where the route's path segments go"
+        )
+    endpoint_glob = _clean(table.get("endpoint_glob"))
+    if endpoint_glob and "{path}" not in endpoint_glob:
+        raise ConfigError(
+            f"knowledge.toml: dependencies.endpoint_glob is {endpoint_glob!r};"
+            " it must contain '{path}' to mark where the endpoint's path goes"
+        )
     return Dependencies(
         route_property=_clean(table.get("route_property")),
         endpoint_property=_clean(table.get("endpoint_property")),
-        route_glob=_clean(table.get("route_glob")),
-        endpoint_glob=_clean(table.get("endpoint_glob")),
+        route_glob=route_glob,
+        endpoint_glob=endpoint_glob,
         absorbed_prefixes=tuple(table.get("absorbed_prefixes", ())),
         dynamic_segment=dynamic_segment,
         dynamic_replacement=_clean(table.get("dynamic_replacement")) or "*",
     )
 
 
 def load_config(root: Path) -> Config:
     with (root / "knowledge.toml").open("rb") as handle:
         data = tomllib.load(handle)
 
     code_repo = _clean(data.get("repo", {}).get("code_repo"))
 
     return Config(
         project_name=_clean(data.get("project", {}).get("name")),
         vocabulary=_vocabulary(data),
diff --git a/tests/test_config.py b/tests/test_config.py
index ab2e6ba..88eb8ef 100644
--- a/tests/test_config.py
+++ b/tests/test_config.py
@@ -111,15 +111,41 @@ def test_unknown_publish_target_is_rejected(tmp_path):
 
 
 def test_dynamic_segment_without_an_ellipsis_is_rejected(tmp_path):
     text = MINIMAL + '\n[dependencies]\ndynamic_segment = "{}"\n'
     with pytest.raises(ConfigError) as exc:
         load_config(write(tmp_path, text))
     assert "dependencies.dynamic_segment" in str(exc.value)
     assert "{}" in str(exc.value)
 
 
 @pytest.mark.parametrize("segment", ["<...>", "[...]"])
 def test_dynamic_segment_alternative_delimiters_are_accepted(tmp_path, segment):
     text = MINIMAL + f'\n[dependencies]\ndynamic_segment = "{segment}"\n'
     config = load_config(write(tmp_path, text))
     assert config.dependencies.dynamic_segment == segment
+
+
+def test_route_glob_without_the_segments_token_is_rejected(tmp_path):
+    text = MINIMAL + '\n[dependencies]\nroute_glob = "app/page.tsx"\n'
+    with pytest.raises(ConfigError) as exc:
+        load_config(write(tmp_path, text))
+    assert "dependencies.route_glob" in str(exc.value)
+    assert "app/page.tsx" in str(exc.value)
+
+
+def test_empty_route_glob_still_loads(tmp_path):
+    config = load_config(write(tmp_path, MINIMAL))
+    assert config.dependencies.route_glob == ""
+
+
+def test_endpoint_glob_without_the_path_token_is_rejected(tmp_path):
+    text = MINIMAL + '\n[dependencies]\nendpoint_glob = "app/api/route.ts"\n'
+    with pytest.raises(ConfigError) as exc:
+        load_config(write(tmp_path, text))
+    assert "dependencies.endpoint_glob" in str(exc.value)
+    assert "app/api/route.ts" in str(exc.value)
+
+
+def test_empty_endpoint_glob_still_loads(tmp_path):
+    config = load_config(write(tmp_path, MINIMAL))
+    assert config.dependencies.endpoint_glob == ""
```
