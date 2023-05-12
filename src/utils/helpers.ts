export class DefaultDict {
    constructor(defaultInit: any) {
      return new Proxy({}, {
        get: (target: any, name: any) => name in target ?
          target[name] :
          (target[name] = typeof defaultInit === 'function' ?
            new defaultInit().valueOf() :
            defaultInit)
      }) as {[k:string]: any}
    }
  }