extends RefCounted
## Read-only adapter for the source checkout's shared JSON/PNG.
## Full Python validation parity and exported/PCK layouts are later milestones.

const ConversationDeck = preload("res://scripts/conversation_deck.gd")
const ObjectModel = preload("res://scripts/object_model.gd")
const EventCatalog = preload("res://scripts/event_catalog.gd")
const VignetteView = preload("res://scripts/vignette_view.gd")
var root: String
var error: String = ""


func fail(message: String) -> Dictionary:
	error = message
	return {}


func path_for(raw: Variant) -> String:
	if not raw is String or raw.strip_edges().is_empty():
		error = "Content path must be a non-empty string"
		return ""
	var relative: String = raw.replace("\\", "/")
	if relative.is_absolute_path() or ":" in relative:
		error = "Content paths must be project-relative: " + relative
		return ""
	var current := root
	for part in relative.split("/"):
		if part == ".." or part.is_empty():
			error = "Unsafe content path: " + relative
			return ""
		if part == ".":
			continue
		var directory := DirAccess.open(current)
		if directory == null or directory.is_link(part):
			error = "Missing directory or unsupported linked path: " + relative
			return ""
		current = current.path_join(part)
	if not FileAccess.file_exists(current) and not DirAccess.dir_exists_absolute(current):
		error = "Missing content: " + relative
		return ""
	return current


func read_json_value(raw: Variant) -> Variant:
	var path := path_for(raw)
	if path.is_empty():
		return null
	var file := FileAccess.open(path, FileAccess.READ)
	if file == null:
		error = "Cannot read JSON: " + str(raw)
		return null
	var parser := JSON.new()
	if parser.parse(file.get_as_text()) != OK:
		error = "Invalid JSON: " + str(raw)
		return null
	return parser.data


func read_json(raw: Variant) -> Dictionary:
	var data: Variant = read_json_value(raw)
	if not error.is_empty():
		return {}
	if not data is Dictionary:
		return fail("Invalid JSON object: " + str(raw))
	return data


func read_image(raw: Variant, crop: bool) -> Image:
	var path := path_for(raw)
	if path.is_empty():
		return null
	var image := Image.new()
	if image.load(path) != OK:
		error = "Cannot load image: " + str(raw)
		return null
	if crop:
		var used := image.get_used_rect()
		if not used.has_area():
			error = "Character image has no visible pixels: " + str(raw)
			return null
		image = image.get_region(used)
	return image


func finite_number(value: Variant) -> bool:
	return (value is float or value is int) and is_finite(float(value))


func vector_data(value: Variant, count: int) -> bool:
	if not value is Array or value.size() != count:
		return false
	for number in value:
		if not finite_number(number):
			return false
	return true


func validate_placements(value: Variant) -> bool:
	if not value is Array:
		error = "Placements must contain an objects array"
		return false
	var ids: Array = []
	var tags: Array = []
	for definition in value:
		if not definition is Dictionary or not definition.get("id") is String or definition.id.strip_edges().is_empty() or definition.id in ids:
			error = "Object IDs must be non-empty and unique"
			return false
		if not definition.get("name", definition.id) is String or not definition.get("tag", "") is String or not definition.get("visible", true) is bool:
			error = "Invalid object name, tag or visibility"
			return false
		if not finite_number(definition.get("width")) or definition.width <= 0 or not finite_number(definition.get("x")) or not finite_number(definition.get("y")):
			error = "Invalid object placement"
			return false
		var tag := ObjectModel.normalize_tag(definition.get("tag", ""))
		if not tag.is_empty() and tag in tags:
			error = "Object tags must be unique"
			return false
		ids.append(definition.id)
		if not tag.is_empty():
			tags.append(tag)
	return true


func load_project(project_root: String) -> Dictionary:
	error = ""
	root = project_root.replace("\\", "/").simplify_path().trim_suffix("/")
	var manifest := read_json("engine_project.json")
	if not error.is_empty():
		return {}
	if manifest.get("schema_version") != 1 or manifest.get("project_type", "standard") != "standard":
		return fail("This first-stage runtime supports standard schema v1 projects only")
	var content: Dictionary = {}
	if manifest.get("content_manifest") != null:
		var external := read_json(manifest.content_manifest)
		if not error.is_empty():
			return {}
		if external.get("schema_version") != 1 or not external.get("content", {}) is Dictionary:
			return fail("Invalid external content manifest")
		content.merge(external.get("content", {}), true)
	if not manifest.get("content", {}) is Dictionary:
		return fail("Inline content must be an object")
	content.merge(manifest.get("content", {}), true)
	var room := read_json(content.get("room"))
	var characters := read_json(content.get("characters"))
	var placements := read_json(content.get("placements"))
	if not error.is_empty():
		return {}
	if room.get("schema_version") != 1 or not room.get("size") is Dictionary:
		return fail("Invalid room schema")
	var size: Dictionary = room.size
	if not finite_number(size.get("width")) or not finite_number(size.get("height")):
		return fail("Room size must be finite")
	if size.width != 960 or size.height != 540:
		return fail("First-stage room size must be 960x540")
	if not vector_data(room.get("movement_bounds"), 4):
		return fail("Invalid movement bounds")
	var limits: Array = room.movement_bounds
	if limits[0] < 0 or limits[1] < 0 or limits[2] <= 0 or limits[3] <= 0 or limits[0] + limits[2] > 960 or limits[1] + limits[3] > 540:
		return fail("Movement bounds must stay inside the room")
	if not room.get("zones") is Dictionary or not vector_data(room.zones.get("water_rest"), 4):
		return fail("Invalid water zone")
	if not room.get("background") is Dictionary or not room.background.get("gradient") is Dictionary or not room.background.get("polygons") is Array:
		return fail("Invalid background")
	var vignette_error := VignetteView.validate(room.background.get("vignette"), Vector2i(size.width, size.height))
	if not vignette_error.is_empty():
		return fail(vignette_error)
	var gradient: Dictionary = room.background.gradient
	if not vector_data(gradient.get("top"), 3) or not vector_data(gradient.get("bottom"), 3) or not finite_number(gradient.get("step")) or gradient.step < 1:
		return fail("Invalid background gradient")
	for polygon in room.background.polygons:
		if not polygon is Dictionary or not vector_data(polygon.get("color"), 3) or not polygon.get("points") is Array or polygon.points.size() < 3:
			return fail("Invalid background polygon")
		for point in polygon.points:
			if not vector_data(point, 2):
				return fail("Invalid polygon point")
	if characters.get("schema_version") != 1 or not characters.get("characters") is Array or characters.characters.size() != 2:
		return fail("First-stage runtime requires two characters")
	var ghost_data: Array = []
	var ids: Array = []
	for definition in characters.characters:
		if not definition is Dictionary or not definition.get("id") is String or not definition.get("display_name") is String:
			return fail("Invalid character metadata")
		if definition.id not in ["kadoka", "maru"] or definition.id in ids:
			return fail("Expected distinct kadoka and maru IDs")
		ids.append(definition.id)
		if not vector_data(definition.get("start_position"), 2) or not finite_number(definition.get("display_height")) or definition.display_height < 16 or definition.display_height > 256:
			return fail("Invalid character position or height")
		if not finite_number(definition.get("personality")) or definition.personality < 0.25 or definition.personality > 3 or not finite_number(definition.get("native_facing")) or absf(float(definition.native_facing)) != 1.0:
			return fail("Invalid personality or native facing")
		if not definition.get("behavior_weights", {}) is Dictionary:
			return fail("Invalid behavior weights")
		for weight in definition.get("behavior_weights", {}).values():
			if not finite_number(weight) or weight < 0 or weight > 100:
				return fail("Behavior weights must be finite and between 0 and 100")
		var image := read_image(definition.get("image"), true)
		if image == null:
			return {}
		ghost_data.append({"definition": definition, "image": image})
	if not validate_placements(placements.get("objects")):
		return {}
	var object_data: Array = []
	for definition in placements.objects:
		var image := read_image(definition.get("image"), false)
		if image == null:
			return {}
		object_data.append({"definition": definition, "image": image})
	var raw_deck: Variant = read_json_value(content.get("conversations"))
	var raw_events := read_json(content.get("events"))
	if not error.is_empty():
		return {}
	var catalog := EventCatalog.parse(raw_events)
	if not catalog.error.is_empty():
		return fail(catalog.error)
	var deck := ConversationDeck.parse(raw_deck, catalog.events)
	if not deck.error.is_empty():
		return fail(deck.error)
	if not finite_number(room.get("conversation_distance")) or room.conversation_distance < 80 or room.conversation_distance > 300:
		return fail("Conversation distance must be between 80 and 300")
	return {"room": room, "characters": ghost_data, "objects": object_data, "conversations": deck.cards, "events": catalog.events, "skipped_conversations": deck.skipped}
