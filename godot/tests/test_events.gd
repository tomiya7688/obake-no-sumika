extends SceneTree

const Loader = preload("res://scripts/content_loader.gd")
const Catalog = preload("res://scripts/event_catalog.gd")
const Deck = preload("res://scripts/conversation_deck.gd")
const GhostModel = preload("res://scripts/ghost_model.gd")
const ObjectModel = preload("res://scripts/object_model.gd")
const Controller = preload("res://scripts/conversation_controller.gd")
const ScriptedEvents = preload("res://scripts/scripted_events.gd")
var checks: int = 0
var failures: Array[String] = []
var data: Dictionary


func _initialize() -> void:
	call_deferred("run_tests")


func check(condition: bool, message: String) -> void:
	checks += 1
	if not condition:
		failures.append(message)
		push_error(message)


func make_pair() -> Array:
	var pair: Array = []
	for item in data.characters:
		var ghost := GhostModel.new(item.definition, Vector2(64, 64), Rect2(74, 80, 812, 446), Rect2(335, 348, 354, 168), 12345)
		ghost.position = Vector2(340 + pair.size() * 120, 300)
		ghost.facing = 1 if pair.is_empty() else -1
		ghost.action = "stop"
		ghost.action_timer = 100
		ghost.velocity = Vector2.ZERO
		pair.append(ghost)
	return pair


func make_objects() -> Array:
	var objects: Array = []
	for item in data.objects:
		objects.append(ObjectModel.new(item.definition))
	return objects


func named(objects: Array, tag: String) -> Variant:
	for item in objects:
		if item.tag == tag:
			return item
	return null


func event_cards(id: String) -> Array:
	return data.conversations.filter(func(card): return card.steps.back().get("event") == id)


func advance(pair: Array, controller: RefCounted) -> void:
	for ghost in pair:
		ghost.step(1.0 / 60)
	controller.step(1.0 / 60)


func until_event(pair: Array, controller: RefCounted, phase: String, frames: int = 2400) -> bool:
	for frame in frames:
		advance(pair, controller)
		if controller.events.phase == phase:
			return true
	return false


func facing_pose(pair: Array) -> bool:
	for ghost in pair:
		var other = pair[1] if ghost == pair[0] else pair[0]
		if ghost.turning or ghost.velocity != Vector2.ZERO or not is_zero_approx(ghost.angle) or (other.position.x - ghost.position.x) * ghost.facing <= 0:
			return false
	return is_equal_approx(pair[0].position.y, pair[1].position.y) and absf(pair[0].position.x - pair[1].position.x) >= 144.9


func run_tests() -> void:
	var loader := Loader.new()
	data = loader.load_project(ProjectSettings.globalize_path("res://").trim_suffix("/").get_base_dir())
	check(not data.is_empty(), "Shared catalog and conversation deck load: " + loader.error)
	if data.is_empty():
		finish()
		return
	check(data.events.size() == 2 and data.conversations.size() == 25 and data.skipped_conversations == 0, "Both existing event cards are now available, with no JSON changes")
	var definition := {"id": "game_device", "label": "ゲーム機", "terminal": true, "required_tag": "game_device"}
	for raw in [null, {}, {"schema_version": 2, "events": [definition]}, {"schema_version": 1, "events": []}, {"schema_version": 1, "events": [definition, definition]}]:
		check(not Catalog.parse(raw).error.is_empty(), "Invalid schema/empty/duplicate catalog is rejected")
	for change in [{"id": " "}, {"label": ""}, {"terminal": "true"}, {"required_tag": 42}]:
		var invalid := definition.duplicate()
		invalid.merge(change, true)
		check(not Catalog.parse({"schema_version": 1, "events": [invalid]}).error.is_empty(), "Invalid event metadata is rejected")
	var normalized := definition.duplicate()
	normalized.required_tag = "  ゲーム 機  "
	check(Catalog.parse({"schema_version": 1, "events": [normalized]}).events.game_device.required_tag == "ゲーム_機", "Catalog tag normalization matches placements")
	var say := {"type": "say", "speaker": "kadoka", "text": "おしまい"}
	var terminal_step := {"type": "event", "event": "game_device"}
	for steps in [[terminal_step, say], [terminal_step, terminal_step], [{"type": "event", "event": "missing"}]]:
		check(not Deck.parse([{"steps": steps}], data.events).error.is_empty(), "Terminal position and unknown event IDs are rejected")
	var legacy := Deck.parse([{"kadoka": "みずあび", "maru": "水浴びするのだ！", "event": "water_bath"}], data.events)
	check(legacy.error.is_empty() and legacy.cards[0].steps.size() == 3 and legacy.cards[0].steps.back().event == "water_bath", "Legacy event card still normalizes through the shared catalog")
	var future: Dictionary = data.events.duplicate(true)
	future["future_event"] = {"id": "future_event", "label": "未移植", "terminal": true, "required_tag": ""}
	var filtered := Deck.parse([{"steps": [say, {"type": "take", "actor": "maru", "tag": "game_device"}, {"type": "event", "event": "future_event"}]}], future)
	check(filtered.cards.is_empty() and filtered.skipped == 1 and filtered.error.is_empty(), "Known but unimplemented event excludes all earlier speech/object actions")
	var pair := make_pair()
	var missing := Controller.new(pair, event_cards("game_device"), 145, [], data.events)
	var before_rng: int = pair[0].rng.state
	check(missing.deck.is_empty() and missing.unavailable_count == 1 and not missing.start(pair[0]) and pair[0].rng.state == before_rng and pair[0].talk_text.is_empty(), "Missing required tag prevents the whole event conversation before partial speech")
	var objects := make_objects()
	var controller := Controller.new(pair, event_cards("water_bath"), 145, objects, data.events)
	check(controller.start(pair[0]) and until_event(pair, controller, "water_bath"), "Shared water conversation reaches bathing")
	var water = named(objects, "water")
	check(facing_pose(pair) and is_equal_approx((pair[0].position.x + pair[1].position.x) * 0.5, water.position.x) and is_equal_approx(pair[0].position.y, water.position.y - 12), "Bathing is horizontal, stopped and facing at the actual water placement")
	var positions: Array = [pair[0].position, pair[1].position]
	var bob: Vector2 = pair[0].draw_position()
	for frame in 60:
		advance(pair, controller)
	check(controller.events.phase == "water_bath" and pair[0].position == positions[0] and pair[1].position == positions[1] and pair[0].draw_position() != bob and facing_pose(pair), "Bathing holds the pose with slow bob only")
	for frame in 600:
		advance(pair, controller)
		if controller.completed_count == 1:
			break
	check(controller.phase == "idle" and controller.completed_count == 1 and controller.last_event == "water_bath" and not pair[0].conversation_controlled and pair[0].talk_cooldown > 0, "Water event completes once and restores random AI")
	pair = make_pair()
	controller = Controller.new(pair, event_cards("water_bath"), 145, [], data.events)
	controller.start(pair[1])
	check(until_event(pair, controller, "water_bath") and facing_pose(pair) and is_equal_approx(pair[0].position.y, pair[0].water.get_center().y - 12), "Without water placement, shared room zone is a valid fallback")
	controller.cancel()
	pair = make_pair()
	objects = make_objects()
	named(objects, "water").position = Vector2.ZERO
	controller = Controller.new(pair, event_cards("water_bath"), 145, objects, data.events)
	controller.start(pair[0])
	check(until_event(pair, controller, "water_bath") and facing_pose(pair) and pair[0].position.x >= pair[0].bounds.position.x and pair[1].position.x <= pair[1].bounds.end.x, "Wall-side water retains full spacing without leaving movement bounds")
	controller.cancel()
	pair = make_pair()
	objects = make_objects()
	var device = named(objects, "game_device")
	controller = Controller.new(pair, event_cards("game_device"), 145, objects, data.events)
	controller.start(pair[1])
	var seen: Array[String] = []
	var stable_speech := true
	var saw_flash := false
	var forward_flee := true
	var fast_flee := false
	var rng_at_flash: Array = []
	var rng_unchanged := true
	for frame in 3000:
		advance(pair, controller)
		for ghost in pair:
			if not ghost.talk_text.is_empty():
				stable_speech = stable_speech and facing_pose(pair)
				if seen.is_empty() or seen.back() != ghost.talk_text:
					seen.append(ghost.talk_text)
		if controller.events.phase == "device_flash":
			saw_flash = device.visible and device.glowing and device.position == Vector2(roundf(pair[1].position.x + pair[1].facing * 42), roundf(pair[1].position.y + 18))
			if rng_at_flash.is_empty():
				rng_at_flash = [pair[0].rng.state, pair[1].rng.state]
		if controller.phase == "event" and not rng_at_flash.is_empty():
			rng_unchanged = rng_unchanged and pair[0].rng.state == rng_at_flash[0] and pair[1].rng.state == rng_at_flash[1]
		if controller.events.phase == "flee":
			for ghost in pair:
				forward_flee = forward_flee and ghost.velocity.x * ghost.facing >= -0.01 and ghost.talk_text.is_empty() and not device.visible and not device.glowing
				fast_flee = fast_flee or ghost.velocity.length() > 150
		if controller.completed_count == 1:
			break
	check(seen == ["これ、なんだろ", "わかんないのだ", "ピカーン", "まぶしいのだーーー", "まぶしい"] and stable_speech, "Device dialogue order is complete; both remain stopped/facing during all speech")
	check(saw_flash and rng_unchanged, "Maru takes out and lights the small device without consuming either RNG stream")
	check(forward_flee and fast_flee and is_equal_approx(pair[0].position.x, pair[0].bounds.position.x) and is_equal_approx(pair[1].position.x, pair[1].bounds.end.x), "After turning, both flee forward at high speed to opposite edges")
	check(controller.phase == "idle" and controller.last_event == "game_device" and not device.visible and not device.glowing and pair[0].target == null and pair[1].target == null, "Normal event completion hides device/light and releases both")
	for cancellation_phase in ["device_wait", "device_flash", "device_maru", "device_kadoka", "flee"]:
		pair = make_pair()
		objects = make_objects()
		var other = named(objects, "found_item")
		other.take_out(Vector2(200, 200), 1)
		var other_state: Dictionary = other.snapshot()
		controller = Controller.new(pair, event_cards("game_device"), 145, objects, data.events)
		controller.start(pair[0])
		check(until_event(pair, controller, cancellation_phase), "Event reaches cancellation stage " + cancellation_phase)
		controller.cancel()
		device = named(objects, "game_device")
		check(not device.visible and not device.glowing and other.snapshot() == other_state and pair[0].target == null and pair[1].target == null and not pair[0].conversation_controlled and controller.completed_count == 0, "Cancel cleans only event-owned device and releases movement: " + cancellation_phase)
	for id in ["water_bath", "game_device"]:
		pair = make_pair()
		objects = make_objects()
		controller = Controller.new(pair, event_cards(id), 145, objects, data.events)
		controller.start(pair[0])
		until_event(pair, controller, "water_move" if id == "water_bath" else "flee")
		controller.events.deadline = 0
		advance(pair, controller)
		check(controller.phase == "idle" and not pair[0].conversation_controlled and not named(objects, "game_device").visible, "Timed-out event restores AI and removes any device: " + id)
	var nonterminal: Dictionary = data.events.duplicate(true)
	nonterminal.water_bath.terminal = false
	var continued := Deck.parse([{"steps": [{"type": "event", "event": "water_bath"}, say]}], nonterminal)
	pair = make_pair()
	controller = Controller.new(pair, continued.cards, 145, make_objects(), nonterminal)
	controller.start(pair[0])
	var continued_speech := false
	for frame in 2400:
		advance(pair, controller)
		if pair[0].talk_text == say.text:
			continued_speech = controller.last_event == "water_bath" and facing_pose(pair)
		if controller.completed_count == 1:
			break
	check(continued.error.is_empty() and continued_speech and controller.completed_count == 1 and controller.phase == "idle", "Nonterminal metadata allows later say only after re-alignment, counting the card once")
	pair = make_pair()
	pair[0].turning = true
	var standalone := ScriptedEvents.new(pair, {}, 145)
	check(not standalone.start("water_bath", data.events.water_bath), "Event cannot start during unfinished rotation")
	await check_scene()
	finish()


func check_scene() -> void:
	var game := (load("res://main.tscn") as PackedScene).instantiate()
	get_root().add_child(game)
	game.set_process(false)
	game.ghosts[0].position = Vector2(340, 350)
	game.ghosts[1].position = Vector2(460, 350)
	game.conversations = Controller.new(game.ghosts, event_cards("water_bath"), 145, game.objects, data.events)
	game.conversations.start(game.ghosts[0])
	check(until_event(game.ghosts, game.conversations, "water_bath"), "Scene reaches water bath")
	game.refresh_views()
	var water_index: int = game.objects.find(named(game.objects, "water"))
	check(water_index >= 0 and game.object_views[water_index].z_index >= 0 and game.object_views[water_index].z_index < game.views[0].z_index, "Spring stays above background but behind bathing ghosts, without covering faces")
	var prefix: String = game.option("screenshot-prefix")
	if not prefix.is_empty() and DisplayServer.get_name() != "headless":
		await RenderingServer.frame_post_draw
		check(get_root().get_texture().get_image().save_png(prefix + "-water.png") == OK, "Water screenshot saves")
	game.conversations.cancel()
	game.conversations = Controller.new(game.ghosts, event_cards("game_device"), 145, game.objects, data.events)
	game.conversations.start(game.ghosts[1])
	check(until_event(game.ghosts, game.conversations, "device_flash"), "Scene reaches lit device")
	game.refresh_views()
	check(game.event_view.glows.size() == 1 and game.object_views.back().visible and game.bubbles[1].visible, "Scene renders device, pixel light rays and Maru's bubble")
	if not prefix.is_empty() and DisplayServer.get_name() != "headless":
		await RenderingServer.frame_post_draw
		check(get_root().get_texture().get_image().save_png(prefix + "-device.png") == OK, "Device screenshot saves")
	game.send_click(Vector2(800, 200))
	game.refresh_views()
	check(game.conversations.phase == "idle" and game.event_view.glows.is_empty() and not game.object_views.back().visible and game.ghosts[0].target != null and game.ghosts[1].target != null, "Click cleans event graphics and sends both to collection targets")
	game.free()


func finish() -> void:
	print("GODOT_EVENT_TESTS checks=", checks, " failures=", failures.size())
	quit(0 if failures.is_empty() else 1)
