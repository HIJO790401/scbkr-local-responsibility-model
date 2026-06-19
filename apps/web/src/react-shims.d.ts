declare module "react" {
  export function useEffect(effect: () => void | (() => void), deps?: unknown[]): void;
  export function useState<T>(initial: T): [T, (value: T) => void];
  export const StrictMode: any;
}

declare module "react/jsx-runtime" {
  export const Fragment: unknown;
  export function jsx(...args: unknown[]): unknown;
  export function jsxs(...args: unknown[]): unknown;
}

declare module "react-dom/client" {
  export function createRoot(container: Element | DocumentFragment): { render(children: unknown): void };
}

declare namespace JSX {
  interface IntrinsicElements {
    [elementName: string]: any;
  }
}
