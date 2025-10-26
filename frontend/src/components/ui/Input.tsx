import clsx from "clsx";
export default function Input(props: React.InputHTMLAttributes<HTMLInputElement>){
  return (
    <input
      className={clsx(
        "w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm shadow-sm",
        "focus:outline-none focus:ring-2 focus:ring-blue-500/60 focus:border-blue-500"
      )}
      {...props}
    />
  );
}
