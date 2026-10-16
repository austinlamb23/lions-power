import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

const components = {
  h1: p => <h1 className="text-2xl font-bold text-white mt-6 mb-3" {...p} />,
  h2: p => <h2 className="text-xl font-bold text-white mt-5 mb-2" {...p} />,
  h3: p => <h3 className="text-lg font-semibold text-white mt-4 mb-2" {...p} />,
  p: p => <p className="text-gray-300 leading-relaxed mb-3" {...p} />,
  a: p => <a className="text-green-400 hover:text-green-300 underline" target="_blank" rel="noreferrer" {...p} />,
  ul: p => <ul className="list-disc list-inside text-gray-300 mb-3 space-y-1" {...p} />,
  ol: p => <ol className="list-decimal list-inside text-gray-300 mb-3 space-y-1" {...p} />,
  blockquote: p => <blockquote className="border-l-2 border-green-700 pl-4 text-gray-400 italic mb-3" {...p} />,
  code: p => <code className="bg-gray-800 text-green-300 rounded px-1 py-0.5 text-sm" {...p} />,
  table: p => (
    <div className="overflow-x-auto mb-4">
      <table className="w-full text-sm border border-gray-700" {...p} />
    </div>
  ),
  th: p => <th className="border border-gray-700 bg-gray-800 text-gray-200 px-2 py-1 text-left" {...p} />,
  td: p => <td className="border border-gray-800 text-gray-300 px-2 py-1" {...p} />,
  strong: p => <strong className="text-white font-semibold" {...p} />,
}

export default function Markdown({ children }) {
  return (
    <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
      {children}
    </ReactMarkdown>
  )
}
