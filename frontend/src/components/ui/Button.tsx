import clsx from "clsx";
type Props = React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "ghost";
};
export default function Button({ className, variant="primary", ...props }: Props){
  const base = "inline-flex items-center justify-center rounded-xl px-4 py-2 text-sm font-medium transition focus:outline-none focus:ring-2 focus:ring-offset-2";
  const styles = {
    primary:  "bg-blue-600 text-white hover:bg-blue-700 focus:ring-blue-600",
    secondary:"bg-slate-900/90 text-white hover:bg-slate-900 focus:ring-slate-900",
    ghost:    "bg-transparent text-slate-700 hover:bg-slate-100 focus:ring-slate-300"
  }[variant];
  return <button className={clsx(base, styles, className)} {...props} />;
}
