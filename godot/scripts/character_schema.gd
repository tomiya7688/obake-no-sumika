extends RefCounted
## Normalize basic shared character data without images, nodes, RNG or writes.
## Python's string-number coercions and filesystem policy are separate boundaries.

var error: String = ""


func fail(message: String) -> Array:
	error = message
	return []


func numeric(value: Variant) -> bool:
	return (value is int or value is float) and is_finite(float(value))


func integer(value: Variant, label: String, minimum: int, maximum: int) -> int:
	if not error.is_empty():
		return 0
	if not numeric(value):
		error = label + " must be a finite number"
		return 0
	# Python int() truncates towards zero. Bound the float before conversion,
	# so even a huge finite JSON number cannot overflow Godot's int64.
	if float(value) < minimum - 1.0 or float(value) > maximum + 1.0:
		error = label + " is outside its allowed range"
		return 0
	var result := int(value)
	if result < minimum or result > maximum:
		error = label + " is outside its allowed range"
	return result


func number(value: Variant, label: String, minimum: float, maximum: float) -> float:
	if not error.is_empty():
		return 0.0
	if not numeric(value) or float(value) < minimum or float(value) > maximum:
		error = label + " must be finite and within its allowed range"
		return 0.0
	return float(value)


func parse(raw: Variant, room_size: Vector2i) -> Array:
	error = ""
	if room_size.x <= 0 or room_size.y <= 0:
		return fail("Room size must be positive")
	if not raw is Dictionary or not numeric(raw.get("schema_version")) or raw.schema_version != 1:
		return fail("Unsupported character schema version")
	if not raw.get("characters") is Array or raw.characters.is_empty():
		return fail("characters must be a non-empty array")
	var results: Array = []
	var ids: Dictionary = {}
	for item in raw.characters:
		if not item is Dictionary:
			return fail("Each character must be an object")
		if not item.get("id") is String or not item.get("display_name") is String:
			return fail("Character id and display_name must be strings")
		var character_id: String = item.id.strip_edges()
		var display_name: String = item.display_name.strip_edges()
		if character_id.is_empty() or display_name.is_empty():
			return fail("Character id and display_name are required")
		if ids.has(character_id):
			return fail("Duplicate character id: " + character_id)
		ids[character_id] = true
		if not item.get("image") is String or item.image.strip_edges().is_empty():
			return fail("Character image must be a non-empty path")
		if not item.get("start_position") is Array or item.start_position.size() != 2:
			return fail("start_position must contain x and y: " + character_id)
		var definition: Dictionary = item.duplicate(true)
		definition.id = character_id
		definition.display_name = display_name
		definition.start_position = [integer(item.start_position[0], "start x", 0, room_size.x), integer(item.start_position[1], "start y", 0, room_size.y)]
		definition.display_height = integer(item.get("display_height"), "display_height", 16, 256)
		definition.personality = number(item.get("personality"), "personality", 0.25, 3.0)
		var facing := integer(item.get("native_facing"), "native_facing", -1, 1)
		definition.native_facing = -1 if facing < 0 else 1
		definition.bubble_y_offset = integer(item.get("bubble_y_offset", 0), "bubble_y_offset", -200, 200)
		if not error.is_empty():
			return []
		if not item.get("behavior_weights", {}) is Dictionary:
			return fail("behavior_weights must be an object")
		var weights: Dictionary = {}
		for action in item.get("behavior_weights", {}):
			if not action is String or action.strip_edges().is_empty():
				return fail("behavior_weights action names must be non-empty strings")
			var normalized_action: String = action.strip_edges()
			if weights.has(normalized_action):
				return fail("behavior_weights action names must be unique")
			weights[normalized_action] = number(item.behavior_weights[action], "behavior weight", 0.0, 100.0)
			if not error.is_empty():
				return []
		definition.behavior_weights = weights
		results.append(definition)
	return results
