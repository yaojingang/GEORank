'use client';

import {useEffect, useRef} from 'react';
import {basicSetup} from 'codemirror';
import {html} from '@codemirror/lang-html';
import {EditorState} from '@codemirror/state';
import {EditorView, keymap} from '@codemirror/view';

type HtmlCodeEditorProps = {
  value: string;
  ariaLabel: string;
  onChange: (value: string) => void;
  onSave: () => void;
};

export function HtmlCodeEditor({value, ariaLabel, onChange, onSave}: HtmlCodeEditorProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const editorRef = useRef<EditorView | null>(null);
  const onChangeRef = useRef(onChange);
  const onSaveRef = useRef(onSave);
  const initialValueRef = useRef(value);

  useEffect(() => {
    onChangeRef.current = onChange;
    onSaveRef.current = onSave;
  }, [onChange, onSave]);

  useEffect(() => {
    if (!containerRef.current) return;
    const editor = new EditorView({
      parent: containerRef.current,
      state: EditorState.create({
        doc: initialValueRef.current,
        extensions: [
          basicSetup,
          html(),
          EditorView.lineWrapping,
          EditorView.contentAttributes.of({'aria-label': ariaLabel}),
          EditorView.updateListener.of((update) => {
            if (update.docChanged) onChangeRef.current(update.state.doc.toString());
          }),
          keymap.of([
            {
              key: 'Mod-s',
              preventDefault: true,
              run: () => {
                onSaveRef.current();
                return true;
              }
            }
          ])
        ]
      })
    });
    editorRef.current = editor;
    return () => {
      editor.destroy();
      editorRef.current = null;
    };
  }, [ariaLabel]);

  useEffect(() => {
    const editor = editorRef.current;
    if (!editor) return;
    const currentValue = editor.state.doc.toString();
    if (currentValue === value) return;
    editor.dispatch({
      changes: {from: 0, to: currentValue.length, insert: value}
    });
  }, [value]);

  return <div className="admin-html-editor__surface" ref={containerRef} />;
}
