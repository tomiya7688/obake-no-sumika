extends SceneTree
## Return real adapter results; the Python harness compares the shared oracle.

const ProjectManifest = preload("res://scripts/project_manifest.gd")


func _initialize() -> void:
	var arguments := OS.get_cmdline_user_args()
	if arguments.size() != 2:
		push_error("Expected request and result JSON filenames")
		quit(1)
		return
	var file := FileAccess.open(arguments[0], FileAccess.READ)
	if file == null:
		push_error("Cannot read manifest requests")
		quit(1)
		return
	var parser := JSON.new()
	if parser.parse(file.get_as_text()) != OK or not parser.data is Array:
		push_error("Invalid manifest requests")
		quit(1)
		return
	var results: Array = []
	# Reuse the adapter: a failed read must not poison the next request.
	var reader := ProjectManifest.new()
	for request in parser.data:
		var result := reader.load_manifest(request.manifest)
		if reader.error.is_empty():
			results.append({"id": request.id, "status": "accepted", "result": result})
		else:
			if not result.is_empty():
				push_error("Failed read returned a partial manifest")
				quit(1)
				return
			results.append({"id": request.id, "status": "rejected", "error": reader.error})
	# FileAccess writes UTF-8; Windows console encodings vary by environment.
	var report := FileAccess.open(arguments[1], FileAccess.WRITE)
	if report == null:
		push_error("Cannot write manifest test report")
		quit(1)
		return
	report.store_string(JSON.stringify(results))
	report.close()
	print("GODOT_MANIFEST_TESTS cases=", results.size())
	quit(0)
