extends RefCounted
## Placement state only. Shared PNGs/JSON remain unchanged by runtime actions.

var id: String
var name: String
var tag: String
var position: Vector2
var home_position: Vector2
var width: float
var visible: bool
var glowing: bool = false


static func normalize_tag(value: String) -> String:
	var whitespace := RegEx.new()
	whitespace.compile("\\s+")
	return whitespace.sub(value.strip_edges(), "_", true)


func _init(definition: Dictionary) -> void:
	id = definition.id
	name = definition.get("name", id)
	tag = normalize_tag(definition.get("tag", ""))
	position = Vector2(definition.x, definition.y)
	home_position = position
	width = float(definition.width)
	visible = definition.get("visible", true)


func move_destination() -> Vector2:
	return position if visible else home_position


func take_out(actor_position: Vector2, facing: int) -> void:
	position = Vector2(roundf(actor_position.x + facing * 42), roundf(actor_position.y + 18))
	visible = true
	glowing = false


func put_away() -> void:
	visible = false
	glowing = false


func snapshot() -> Dictionary:
	return {"id": id, "tag": tag, "x": position.x, "y": position.y, "visible": visible, "glowing": glowing}
