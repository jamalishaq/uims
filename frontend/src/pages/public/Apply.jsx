import useTitle from '../../hooks/useTitle'

export default function Apply() {
  useTitle('Apply for Admission')

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-50 dark:bg-slate-950 p-4">
      <div className="w-full max-w-lg text-center">
        <div className="inline-flex items-center justify-center w-12 h-12 rounded-2xl bg-indigo-600 mb-4">
          <span className="text-white font-bold text-lg">U</span>
        </div>
        <h1 className="text-2xl font-semibold text-slate-900 dark:text-slate-100 mb-2">
          Apply for Admission
        </h1>
        <p className="text-slate-500 dark:text-slate-400 text-sm">
          Application form coming soon.
        </p>
      </div>
    </div>
  )
}
