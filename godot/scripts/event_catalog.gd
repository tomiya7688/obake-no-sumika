extends RefCounted
## Catalog metadata is shared data; implemented handlers are a runtime capability.

const ObjectModel = preload("res://scripts/object_model.gd")
const IMPLEMENTED := ["water_bath", "game_device"]


static func parse(raw: Variant) -> Dictionary:
	var result := {"events": {}, "error": ""}
	if not raw is Dictionary or raw.get("schema_version") != 1 or not raw.get("events") is Array or raw.events.is_empty():
		result.error = "Invalid event catalog schema or empty events"
		return result
	for entry in raw.events:
		if not entry is Dictionary or not entry.get("id") is String or not entry.get("label") is String or entry.id.strip_edges().is_empty() or entry.label.strip_edges().is_empty():
			result.error = "Event id and label must be non-empty strings"
			return result
		var id: String = entry.id.strip_edges()
		if result.events.has(id) or not entry.get("terminal", false) is bool:
			result.error = "Event IDs must be unique and terminal must be boolean"
			return result
		var tag: Variant = entry.get("required_tag")
		if tag != null and not tag is String:
			result.error = "Event required_tag must be a string or null"
			return result
		result.events[id] = {"id": id, "label": entry.label.strip_edges(), "terminal": entry.get("terminal", false), "required_tag": ObjectModel.normalize_tag(tag) if tag != null else ""}
	return result
