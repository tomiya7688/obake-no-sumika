extends RefCounted
## Validate RGB palette and gradient spacing without drawing or file writes.
## Polygon geometry and vignette settings are validated separately.

var error: String = ""


func fail(message: String) -> Dictionary:
	error = message
	return {}


func integer(value: Variant, label: String, maximum: int) -> int:
	if not error.is_empty():
		return 0
	if not (value is int or value is float) or not is_finite(float(value)):
		error = label + " must be a finite integer value"
		return 0
	var number := float(value)
	if number < 0 or number > maximum or floor(number) != number:
		error = label + " must be an integer value within its allowed range"
		return 0
	return int(value)


func color(value: Variant, label: String) -> Array:
	if not value is Array or value.size() != 3:
		error = label + " must contain red, green and blue"
		return []
	var result := [integer(value[0], label + " red", 255), integer(value[1], label + " green", 255), integer(value[2], label + " blue", 255)]
	return result if error.is_empty() else []


func parse(raw: Variant, room_height: int) -> Dictionary:
	error = ""
	if room_height < 1 or room_height > 2160:
		return fail("Room height must be between 1 and 2160")
	if not raw is Dictionary or not raw.get("gradient") is Dictionary:
		return fail("background.gradient must be an object")
	if not raw.get("polygons") is Array:
		return fail("background.polygons must be an array")
	var result: Dictionary = raw.duplicate(true)
	result.gradient.top = color(raw.gradient.get("top"), "background.gradient.top")
	result.gradient.bottom = color(raw.gradient.get("bottom"), "background.gradient.bottom")
	result.gradient.step = integer(raw.gradient.get("step"), "background.gradient.step", room_height)
	if not error.is_empty():
		return {}
	if result.gradient.step == 0:
		return fail("background.gradient.step must be between 1 and room height")
	for index in raw.polygons.size():
		var layer: Variant = raw.polygons[index]
		if not layer is Dictionary:
			return fail("background.polygons entries must be objects")
		result.polygons[index].color = color(layer.get("color"), "background.polygons[%d].color" % index)
		if not error.is_empty():
			return {}
	return result
