import clsx from "clsx";
export function Card({className, ...p}: React.HTMLAttributes<HTMLDivElement>){
  return <div className={clsx("rounded-2xl bg-white shadow-sm border border-slate-100", className)} {...p} />;
}
export function CardHeader({className, ...p}: React.HTMLAttributes<HTMLDivElement>){
  return <div className={clsx("px-5 pt-5", className)} {...p} />;
}
export function CardTitle({className, ...p}: React.HTMLAttributes<HTMLHeadingElement>){
  return <h3 className={clsx("text-base font-semibold text-slate-900", className)} {...p} />;
}
export function CardContent({className, ...p}: React.HTMLAttributes<HTMLDivElement>){
  return <div className={clsx("px-5 pb-5", className)} {...p} />;
}
