type AuthInputProps = React.InputHTMLAttributes<HTMLInputElement> & { label: string };

export function AuthInput({ label, ...props }: AuthInputProps) {
  return <label className="block text-sm font-medium text-slate-300">{label}<input {...props} className="mt-2 h-11 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 text-sm text-white outline-none placeholder:text-slate-600 focus:border-cyan-400" /></label>;
}
