import * as React from 'react';

export type ToastType = 'default' | 'success' | 'error' | 'warning' | 'info';

export interface Toast {
  id: string;
  title?: string;
  description?: string;
  type?: ToastType;
  duration?: number;
}

export interface ToastState {
  toasts: Toast[];
}

type ToastAction =
  | { type: 'ADD_TOAST'; toast: Toast }
  | { type: 'REMOVE_TOAST'; id: string }
  | { type: 'CLEAR_TOASTS' };

const toastReducer = (state: ToastState, action: ToastAction): ToastState => {
  switch (action.type) {
    case 'ADD_TOAST':
      return {
        ...state,
        toasts: [...state.toasts, action.toast],
      };
    case 'REMOVE_TOAST':
      return {
        ...state,
        toasts: state.toasts.filter((t) => t.id !== action.id),
      };
    case 'CLEAR_TOASTS':
      return {
        ...state,
        toasts: [],
      };
    default:
      return state;
  }
};

let toastCount = 0;
const genId = () => {
  toastCount = (toastCount + 1) % Number.MAX_SAFE_INTEGER;
  return toastCount.toString();
};

// Global state for toasts
const listeners: Array<(state: ToastState) => void> = [];
let memoryState: ToastState = { toasts: [] };

function dispatch(action: ToastAction) {
  memoryState = toastReducer(memoryState, action);
  listeners.forEach((listener) => {
    listener(memoryState);
  });
}

export interface ToastOptions {
  title?: string;
  description?: string;
  type?: ToastType;
  duration?: number;
}

function toast(options: ToastOptions) {
  const id = genId();
  const toastItem: Toast = {
    id,
    title: options.title,
    description: options.description,
    type: options.type || 'default',
    duration: options.duration || 5000,
  };

  dispatch({ type: 'ADD_TOAST', toast: toastItem });

  // Auto-remove after duration
  if (toastItem.duration && toastItem.duration > 0) {
    setTimeout(() => {
      dispatch({ type: 'REMOVE_TOAST', id });
    }, toastItem.duration);
  }

  return {
    id,
    dismiss: () => dispatch({ type: 'REMOVE_TOAST', id }),
  };
}

toast.success = (options: Omit<ToastOptions, 'type'>) => toast({ ...options, type: 'success' });
toast.error = (options: Omit<ToastOptions, 'type'>) => toast({ ...options, type: 'error' });
toast.warning = (options: Omit<ToastOptions, 'type'>) => toast({ ...options, type: 'warning' });
toast.info = (options: Omit<ToastOptions, 'type'>) => toast({ ...options, type: 'info' });

function useToast() {
  const [state, setState] = React.useState<ToastState>(memoryState);

  React.useEffect(() => {
    listeners.push(setState);
    return () => {
      const index = listeners.indexOf(setState);
      if (index > -1) {
        listeners.splice(index, 1);
      }
    };
  }, []);

  return {
    toasts: state.toasts,
    toast,
    dismiss: (id: string) => dispatch({ type: 'REMOVE_TOAST', id }),
    clearAll: () => dispatch({ type: 'CLEAR_TOASTS' }),
  };
}

export { useToast, toast };
