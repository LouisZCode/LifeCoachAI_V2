import { useEffect, useRef, useState } from 'react'
import { EditorContent, useEditor } from '@tiptap/react'
import StarterKit from '@tiptap/starter-kit'
import { api } from '../api'
import type { SessionDocument, TiptapDoc } from '../api'

/** Rich editor for one generated document. Maria edits directly; changes
 * autosave (debounced) back to the document row. */
export default function DocEditor({ document }: { document: SessionDocument }) {
  const [saveState, setSaveState] = useState<'saved' | 'saving' | 'error'>('saved')
  const timer = useRef<ReturnType<typeof setTimeout>>(undefined)

  const editor = useEditor(
    {
      extensions: [StarterKit],
      content: document.content,
      editorProps: {
        attributes: {
          class: 'doc-editor min-h-[16rem] outline-none',
        },
      },
      onUpdate: ({ editor }) => {
        setSaveState('saving')
        clearTimeout(timer.current)
        timer.current = setTimeout(() => {
          api
            .updateDocument(document.id, { content: editor.getJSON() as TiptapDoc })
            .then(() => setSaveState('saved'))
            .catch(() => setSaveState('error'))
        }, 800)
      },
    },
    [document.id],
  )

  useEffect(() => () => clearTimeout(timer.current), [])

  return (
    <div>
      <div className="mb-2 flex justify-end">
        <span
          className={`font-heading text-xs font-bold uppercase tracking-wide ${
            saveState === 'error' ? 'text-accent' : 'text-ink/40'
          }`}
        >
          {saveState === 'saved' ? 'Saved' : saveState === 'saving' ? 'Saving…' : 'Not saved — check connection'}
        </span>
      </div>
      <EditorContent editor={editor} />
    </div>
  )
}
