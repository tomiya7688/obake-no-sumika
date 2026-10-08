extends RefCounted
## Read-only project definition adapter for spec/engine/project_manifest.md.
## Returned paths are normalized root-relative strings. No script is executed.
## Source-checkout policy rejects absolute field paths and all linked paths.

var root: String = ""
var error: String = ""


func fail(message: String) -> Dictionary:
	error = message
	return {}


func relative_path(raw: Variant, file_only: bool = false) -> String:
	if not raw is String or raw.strip_edges().is_empty():
		error = "Project paths must be non-empty strings"
		return ""
	var relative: String = raw.replace("\\", "/")
	if relative.is_absolute_path() or ":" in relative:
		error = "Project paths must be relative: " + relative
		return ""
	var current := root
	var components: Array[String] = []
	# Inspect every component BEFORE normalizing '..': a link/../file must
	# not hide a linked reference. Links remain unsupported even inside root.
	for part in relative.split("/", false):
		if part == ".":
			continue
		if part == "..":
			if components.is_empty():
				error = "Path escapes the project root: " + relative
				return ""
			if not DirAccess.dir_exists_absolute(current):
				error = "Missing directory in project path: " + relative
				return ""
			components.pop_back()
			current = root if components.is_empty() else root.path_join("/".join(components))
			continue
		var directory := DirAccess.open(current)
		if directory == null or directory.is_link(part):
			error = "Missing directory or unsupported linked path: " + relative
			return ""
		current = current.path_join(part)
		components.append(part)
	if not FileAccess.file_exists(current) and not DirAccess.dir_exists_absolute(current):
		error = "Project path does not exist: " + relative
		return ""
	if file_only and not FileAccess.file_exists(current):
		error = "Project path must be a file: " + relative
		return ""
	return "." if components.is_empty() else "/".join(components)


func read_object(relative: String) -> Dictionary:
	var file := FileAccess.open(root.path_join(relative), FileAccess.READ)
	if file == null:
		return fail("Cannot read project JSON: " + relative)
	var parser := JSON.new()
	if parser.parse(file.get_as_text()) != OK:
		return fail("Invalid project JSON: " + relative)
	if not parser.data is Dictionary:
		return fail("Project JSON must contain an object: " + relative)
	return parser.data


func schema_one(raw: Dictionary) -> bool:
	var version: Variant = raw.get("schema_version")
	return (version is int or version is float) and version == 1


func trimmed_text(raw: Variant) -> String:
	return raw.strip_edges() if raw is String else ""


func content_paths(raw: Variant) -> Dictionary:
	if not raw is Dictionary:
		return fail("content must be an object")
	var content: Dictionary = {}
	for raw_name in raw:
		var name := trimmed_text(raw_name)
		if name.is_empty():
			return fail("Content names must not be empty")
		var path := relative_path(raw[raw_name])
		if not error.is_empty():
			return {}
		content[name] = path
	return content


func editor_definitions(raw: Variant) -> Array:
	if not raw is Array:
		error = "editors must be an array"
		return []
	var editors: Array = []
	var ids: Array[String] = []
	for definition in raw:
		if not definition is Dictionary:
			error = "Each editor must be an object"
			return []
		var id := trimmed_text(definition.get("id"))
		var label := trimmed_text(definition.get("label"))
		if id.is_empty() or label.is_empty() or id in ids:
			error = "Editor id/label must be non-empty and IDs unique"
			return []
		var script := relative_path(definition.get("script"), true)
		if not error.is_empty():
			return []
		ids.append(id)
		editors.append({"id": id, "label": label, "script": script})
	return editors


func load_manifest(manifest_path: String) -> Dictionary:
	error = ""
	root = ""
	var absolute := manifest_path.replace("\\", "/")
	if not absolute.is_absolute_path():
		return fail("The manifest filename must be an absolute filesystem path")
	root = absolute.get_base_dir().simplify_path()
	if root.ends_with(":"):
		root += "/"
	if root != "/" and not root.ends_with(":/"):
		root = root.trim_suffix("/")
	var filename := relative_path(absolute.get_file(), true)
	if not error.is_empty():
		return {}
	var raw := read_object(filename)
	if not error.is_empty():
		return {}
	if not schema_one(raw):
		return fail("Unsupported project schema version")
	var name := trimmed_text(raw.get("name"))
	if name.is_empty():
		return fail("Project name is required")
	var project_type := trimmed_text(raw.get("project_type", "standard"))
	if raw.get("project_type") == null:
		project_type = "standard"
	var whitespace := RegEx.new()
	whitespace.compile("\\s")
	if project_type.is_empty() or whitespace.search(project_type) != null:
		return fail("project_type must be non-empty without internal whitespace")
	var entrypoint := relative_path(raw.get("entrypoint"), true)
	if not error.is_empty():
		return {}
	var editors := editor_definitions(raw.get("editors", []))
	if not error.is_empty():
		return {}
	var content_manifest: Variant = null
	var external_content: Dictionary = {}
	if raw.get("content_manifest") != null:
		content_manifest = relative_path(raw.content_manifest, true)
		if not error.is_empty():
			return {}
		var external := read_object(content_manifest)
		if not error.is_empty():
			return {}
		if not schema_one(external):
			return fail("Unsupported content manifest schema version")
		external_content = content_paths(external.get("content", {}))
		if not error.is_empty():
			return {}
	var inline_content := content_paths(raw.get("content", {}))
	if not error.is_empty():
		return {}
	# Validate BOTH maps before overriding, including unused/overridden paths.
	external_content.merge(inline_content, true)
	return {"schema_version": 1, "name": name, "project_type": project_type,
		"entrypoint": entrypoint, "editors": editors, "content": external_content,
		"content_manifest": content_manifest}
