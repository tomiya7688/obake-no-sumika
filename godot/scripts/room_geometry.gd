extends RefCounted
## Validate basic room geometry without images, nodes, RNG or file writes.
## Background/motes and the first-stage runtime restrictions are separate.

var error: String = ""


func fail(message: String) -> Dictionary:
	error = message
	return {}


func numeric(value: Variant) -> bool:
	return (value is int or value is float) and is_finite(float(value))


func integer(value: Variant, label: String, minimum: int, maximum: int) -> int:
	if not error.is_empty():
		return 0
	if not numeric(value):
		error = label + " must be a finite integer value"
		return 0
	var number := float(value)
	# JSON numbers are floats in Godot. Reject fractions and bound before the
	# int64 conversion, including rectangle coordinates that Python leaves unbounded.
	if number < minimum or number > maximum or floor(number) != number:
		error = label + " must be an integer value within its allowed range"
		return 0
	return int(value)


func rectangle(value: Variant, label: String, size: Vector2i) -> Array:
	if not value is Array or value.size() != 4:
		error = label + " must contain x, y, width and height"
		return []
	var x := integer(value[0], label + " x", 0, size.x)
	var y := integer(value[1], label + " y", 0, size.y)
	var width := integer(value[2], label + " width", 1, size.x)
	var height := integer(value[3], label + " height", 1, size.y)
	if not error.is_empty():
		return []
	if x + width > size.x or y + height > size.y:
		error = label + " must stay inside the room"
		return []
	return [x, y, width, height]


func parse(raw: Variant) -> Dictionary:
	error = ""
	if not raw is Dictionary or not numeric(raw.get("schema_version")) or raw.schema_version != 1:
		return fail("Unsupported room schema version")
	if not raw.get("size") is Dictionary:
		return fail("size must be an object")
	var width := integer(raw.size.get("width"), "width", 320, 3840)
	var height := integer(raw.size.get("height"), "height", 180, 2160)
	if not error.is_empty():
		return {}
	if width * 9 != height * 16:
		return fail("Room size must use a 16:9 aspect ratio")
	var size := Vector2i(width, height)
	var fps := integer(raw.get("fps"), "fps", 1, 240)
	var movement := rectangle(raw.get("movement_bounds"), "movement_bounds", size)
	if not error.is_empty():
		return {}
	if not raw.get("zones") is Dictionary:
		return fail("zones must be an object")
	var water := rectangle(raw.zones.get("water_rest"), "zones.water_rest", size)
	if not error.is_empty():
		return {}
	var distance: Variant = raw.get("conversation_distance")
	if not numeric(distance) or float(distance) < 1.0 or float(distance) > width:
		return fail("conversation_distance must be finite and between 1 and room width")
	var result: Dictionary = raw.duplicate(true)
	result.size.width = width
	result.size.height = height
	result.fps = fps
	result.movement_bounds = movement
	result.zones.water_rest = water
	result.conversation_distance = float(distance)
	return result
