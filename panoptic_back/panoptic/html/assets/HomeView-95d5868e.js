import{d as j,u as I,r as g,c as y,o,a as n,b as e,t as l,e as m,w as F,v as T,n as B,M as S,g as P,p as E,f as O,_ as V,F as b,h as H,i as z,j as A,k as C,l as $,m as L,q as w,s as R,x as M,D as q}from"./index-171002d8.js";import{_ as U}from"./Tutorial-6dd5dd2e.js";const N=a=>(E("data-v-9d2b8ee6"),a=a(),O(),a),W={class:""},G={class:"mb-3"},J={class:"d-flex text-start input mb-2"},K={class:"info"},Q={key:0},X={key:1,class:"text-placeholder"},Y=N(()=>e("i",{class:"bi bi-folder"},null,-1)),Z=[Y],ee={class:"d-flex text-start input"},te={class:"info"},se={class:"flex-grow-1 value text-dim"},oe={class:"d-flex mt-2"},ae=N(()=>e("div",{class:"flex-grow-1"},null,-1)),ne=j({__name:"Create",emits:["cancel","create"],setup(a,{emit:s}){const _=I(),p=s,c=g(""),u=g(""),v=y(()=>c.value!=""&&u.value!="");function h(i){i&&(c.value=i)}function x(){_.showModal(S.FOLDERSELECTION,{callback:h,mode:"create"})}return(i,t)=>(o(),n("div",W,[e("h3",G,l(i.$t("main.home.create_title")),1),e("div",J,[e("div",K,l(i.$t("main.home.label.folder")),1),e("div",{class:"flex-grow-1 value text-dim",style:{cursor:"pointer"},onClick:x},[c.value!=""?(o(),n("span",Q,l(c.value),1)):(o(),n("span",X,l(i.$t("main.home.label.path_placeholder")),1))]),e("div",{id:"select-folder",class:"folder",style:{cursor:"pointer"},onClick:t[0]||(t[0]=r=>{x(),m(P)()})},Z)]),e("div",ee,[e("div",te,l(i.$t("main.home.label.name")),1),e("div",se,[F(e("input",{type:"text","onUpdate:modelValue":t[1]||(t[1]=r=>u.value=r),placeholder:"project_name",style:{width:"100%"}},null,512),[[T,u.value]])])]),e("div",oe,[ae,e("div",{class:"btn-grey hover-grey",onClick:t[2]||(t[2]=r=>p("cancel"))},l(i.$t("main.home.label.cancel")),1),e("div",{id:"confirm-create",class:B(["ms-2",v.value?"btn-blue":"btn-grey text-dim"]),onClick:t[3]||(t[3]=r=>{p("create",{path:c.value,name:u.value}),m(P)()})},l(i.$t("main.home.label.create")),3)])]))}});const ie=V(ne,[["__scopeId","data-v-9d2b8ee6"]]),D=a=>(E("data-v-f878743d"),a=a(),O(),a),le={class:"create-option d-flex"},ce=D(()=>e("div",{class:"flex-grow-1"},[e("h6",{class:"create-title m-0"},"Créer un nouveau projet"),e("span",{class:"create-explanation"},"Créer un nouveau projet panoptic dans un dossier.")],-1)),re=D(()=>e("div",{class:"flex-grow-1"},[e("h6",{class:"create-title m-0"},"Importer un projet"),e("span",{class:"create-explanation"},"Choisissez un dossier Panoptic existant.")],-1)),de=j({__name:"Options",emits:["create","import"],setup(a,{emit:s}){const _=I(),p=s;function c(v){v&&p("import",v)}function u(){_.showModal(S.FOLDERSELECTION,{callback:c,mode:"import"})}return(v,h)=>(o(),n(b,null,[e("div",le,[ce,e("div",{id:"create-project",class:"create-btn highlight",onClick:h[0]||(h[0]=x=>{p("create"),m(P)()})},"Créer")]),e("div",{class:"create-option d-flex"},[re,e("div",{class:"create-btn",onClick:u},"Importer")])],64))}});const _e=V(de,[["__scopeId","data-v-f878743d"]]),f=a=>(E("data-v-437ca581"),a=a(),O(),a),pe={class:"window d-flex"},ue={key:0,class:"project-menu"},me={class:"d-flex"},ve=["onClick"],he={class:"m-0"},fe={class:"m-0 p-0 text-wrap text-break dimmed-2",style:{"font-size":"13px"}},xe={class:"project-option flex-shrink-0"},$e=f(()=>e("i",{class:"bi bi-three-dots-vertical"},null,-1)),be={class:"text-start"},ke=["onClick"],Ce=f(()=>e("i",{class:"bi bi-trash me-1"},null,-1)),we={key:1,class:"main-menu flex-grow-1"},ge=f(()=>e("div",{class:"icon"},"👀",-1)),ye=f(()=>e("h1",{class:"m-0 p-0"},"Panoptic",-1)),Pe=f(()=>e("h6",{class:"dimmed-2"},"Version 0.3",-1)),je={id:"main-menu",class:"create-menu mt-5 pt-5"},Ie={class:"plugin-preview mt-5"},Se={class:"ps-1"},Ee=["onClick"],Oe={key:2,class:"text-center mt-5 w-100"},Ve=f(()=>e("p",null,"Waiting for Server...",-1)),Le=[Ve],Me=j({__name:"HomeView",setup(a){const s=I();H();const _=g(0),p=y(()=>Array.isArray(s.data.status.projects)&&s.data.status.projects.length>0),c=y(()=>!p.value&&s.data.init);function u(t){return t.replaceAll("-","‑")}function v(t){t.path&&t.name&&s.createProject(t.path,t.name)}function h(t){s.importProject(t)}function x(t){s.delPlugin(t)}function i(){s.showModal(S.FOLDERSELECTION,{mode:"create",callback:s.addPlugin})}return z(()=>{s.isProjectLoaded&&A.push("/view")}),(t,r)=>(o(),n(b,null,[c.value?(o(),C(U,{key:0})):$("",!0),e("div",pe,[p.value?(o(),n("div",ue,[(o(!0),n(b,null,L(m(s).data.status.projects,d=>(o(),n("div",me,[e("div",{class:"project flex-grow-1 overflow-hidden",onClick:k=>m(s).loadProject(d.path)},[e("h5",he,l(d.name),1),e("div",fe,l(u(d.path)),1)],8,ve),e("div",xe,[R(q,null,{button:M(()=>[$e]),popup:M(({hide:k})=>[e("div",be,[e("div",{onClick:Ne=>{m(s).deleteProject(d.path),k()},class:"m-1 base-hover p-1"},[Ce,w("delete")],8,ke)])]),_:2},1024)])]))),256))])):$("",!0),m(s).data.init?(o(),n("div",we,[ge,ye,Pe,e("div",je,[_.value==0?(o(),C(_e,{key:0,onCreate:r[0]||(r[0]=d=>_.value=1),onImport:h})):$("",!0),_.value==1?(o(),C(ie,{key:1,onCancel:r[1]||(r[1]=d=>_.value=0),onCreate:v})):$("",!0),e("div",Ie,[e("h5",{class:"text-center"},[w(" Plugins "),e("span",{class:"sb bi bi-plus",style:{position:"relative",top:"1px"},onClick:i})]),(o(!0),n(b,null,L(m(s).data.plugins,d=>(o(),n("div",Se,[e("span",{onClick:k=>x(d),class:"bi bi-x base-hover"},null,8,Ee),w(" "+l(d),1)]))),256))])])])):(o(),n("div",Oe,Le))])],64))}});const Te=V(Me,[["__scopeId","data-v-437ca581"]]);export{Te as default};