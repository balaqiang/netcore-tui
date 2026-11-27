# Skill: textual-screen

## Trigger
Creating or modifying a screen, modal or reusable widget.

## Steps
1. Locate the screen in `docs/UI_SPEC.md §5` — copy its `id`, number
   key, layout, actions and service.
2. Create `src/netcore/tui/screens/<name>.py`:

   ```python
   class RoutingScreen(Screen[None]):
       BINDINGS = [
           Binding("n", "add_route", "Add route"),
           Binding("d", "delete_route", "Delete"),
           Binding("r", "refresh", "Refresh"),
       ]

       def __init__(self, routing: RoutingService) -> None:
           super().__init__(id="routing")
           self._routing = routing

       def compose(self) -> ComposeResult: ...

       def on_screen_resume(self) -> None:
           self.action_refresh()

       @work(thread=True, exclusive=True, group="routing")
       def action_refresh(self) -> None:
           routes = self._routing.routes(self._selected_router_id)
           self.app.call_from_thread(self._render_routes, routes)
   ```

3. Inject services through the constructor (from `NetCoreApp`), never
   construct infrastructure inside the TUI.
4. Put styles in `theme.tcss` with screen-scoped selectors (`#routing DataTable`).
5. Handle `ApplicationError` → inline error / `notify(severity="error")`.
6. Implement empty, loading and error states (UI_SPEC §9).
7. Add Pilot test:

   ```python
   async def test_routing_add_modal_opens(app_factory):
       app = app_factory()
       async with app.run_test(size=(120, 40)) as pilot:
           await pilot.press("4", "n")
           assert app.screen.id == "route-form"
           await pilot.press("escape")
           assert app.screen.id == "routing"
   ```

## Checks
- Screen reachable by its number key.
- No imports from `netcore.domain` (except enums via DTO module) or
  `netcore.infrastructure`.
- UI stays responsive while worker runs (no blocking call in handlers).
