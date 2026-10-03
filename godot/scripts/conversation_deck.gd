extends RefCounted
## Read the shared deck without rewriting or partially executing unsupported cards.

const ObjectModel = preload("res://scripts/object_model.gd")

static func parse(raw: Variant) -> Dictionary:
	var result := {"cards": [], "skipped": 0, "error": ""}
	if not raw is Array:
		result.error = "Conversation deck must be an array"
		return result
	var whitespace := RegEx.new()
	whitespace.compile("\\s+")
	for index in raw.size():
		var entry: Variant = raw[index]
		if not entry is Dictionary:
			result.error = "Conversation must be an object: " + str(index + 1)
			return result
		var weight: Variant = entry.get("weight", 1)
		if not (weight is float or weight is int) or not is_finite(float(weight)) or weight < 1 or weight > 999:
			result.error = "Conversation weight must be finite and between 1 and 999"
			return result
		var raw_steps: Variant = entry.get("steps")
		if raw_steps == null:
			raw_steps = []
			for speaker in ["kadoka", "maru"]:
				if entry.get(speaker) is String and not entry[speaker].strip_edges().is_empty():
					raw_steps.append({"type": "say", "speaker": speaker, "text": entry[speaker]})
			if entry.has("event"):
				raw_steps.append({"type": "event", "event": entry.event})
		if not raw_steps is Array or raw_steps.is_empty():
			result.error = "Conversation must contain steps"
			return result
		var steps: Array = []
		var unsupported := false
		for step in raw_steps:
			if not step is Dictionary:
				result.error = "Conversation step must be an object"
				return result
			var kind: Variant = step.get("type", "say")
			if kind == "event":
				unsupported = true
				continue
			if kind in ["move", "take", "put"]:
				if step.get("actor", "kadoka") not in ["kadoka", "maru", "both"] or not step.get("tag") is String or step.tag.strip_edges().is_empty():
					result.error = "Object step requires a known actor and non-empty tag"
					return result
				steps.append({"type": kind, "actor": step.get("actor", "kadoka"), "tag": ObjectModel.normalize_tag(step.tag)})
				continue
			if kind != "say" or step.get("speaker", "kadoka") not in ["kadoka", "maru"] or not step.get("text") is String or step.text.strip_edges().is_empty():
				result.error = "Invalid say step or unknown step type"
				return result
			steps.append({"type": "say", "speaker": step.get("speaker", "kadoka"), "text": whitespace.sub(step.text.strip_edges(), " ", true)})
		if unsupported:
			result.skipped += 1
		else:
			result.cards.append({"weight": float(weight), "steps": steps})
	return result
