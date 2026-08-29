import {useEffect,useRef} from 'react';
import '@argws/visual-builder';
import '@argws/visual-builder/styles.css';
export default function ArgwsPage({documentUrl='/api/pages/home'}) {
  const ref=useRef(null);
  useEffect(()=>{fetch(documentUrl).then(r=>r.json()).then(p=>{ref.current.document=p.data?.document??p.document??p;});},[documentUrl]);
  return <argws-page-renderer ref={ref}></argws-page-renderer>;
}
