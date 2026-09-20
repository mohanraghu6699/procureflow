import { useEffect, type RefObject } from "react";

/**
 * While `open`, calls `onDismiss` when the user presses Escape or presses anywhere outside `ref`.
 *
 * Listening on the document (rather than covering the page with a click-catching layer) means the dismissal
 * also works when the press lands on something that sits above the layer, such as the sidebar.
 */
export function useDismiss(ref: RefObject<HTMLElement | null>, open: boolean, onDismiss: () => void) {
  useEffect(() => {
    if (!open) return;

    function onPointerDown(event: PointerEvent) {
      if (ref.current && !ref.current.contains(event.target as Node)) onDismiss();
    }
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") onDismiss();
    }

    document.addEventListener("pointerdown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("pointerdown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [ref, open, onDismiss]);
}
