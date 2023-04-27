// interface InputNode {
//     parent: InputNode
//     children?: {[index: number | string]: InputNode}
//     inputElem?: HTMLElement
// }

class InputNode {
    index: number
    parent: InputNode
    children: { [index: number | string]: InputNode }
    inputElem: HTMLElement
    constructor(index: number, parent: InputNode, inputElem: HTMLElement = undefined) {
        this.index = index
        this.parent = parent
        this.inputElem = inputElem
        this.children = {}
    }
    hasChildren() {
        return Object.keys(this.children).length > 0
    }
    hasParent() {
        return this.parent != undefined
    }
    hasElem() {
        return this.inputElem != undefined
    }
    nextInput(depth = 0): InputNode {
        if(!this.hasParent()) {
            return
        }
        // select first child in parent element with an index bigger than its own
        let next = this.parent.sortedChildren().find(n => n.index > this.index)
        let parent = this.parent

        // while no possible next input is found search closer to root
        while(next == undefined && depth > 0 && parent != undefined) {
            next = parent.nextInput()
            depth -= 1
            parent = parent.parent
        }
        // if node is a group select the first input in this group
        if(next && next.hasChildren()) {
            next = next.firstInput()
        }
        return next
    }
    prevInput(depth = 0): InputNode {
        if(!this.hasParent()) {
            return
        }
        // select first child in parent element with an index bigger than its own
        let next = this.parent.sortedChildren().findLast(n => n.index < this.index)
        let parent = this.parent

        // while no possible next input is found search closer to root
        while(next == undefined && depth > 0 && parent != undefined) {
            next = parent.prevInput()
            depth -= 1
            parent = parent.parent
        }
        // if node is a group select the last input in this group
        if(next && next.hasChildren()) {
            next = next.lastInput()
        }
        return next
    }
    sortedChildren() {
        return Object.values(this.children).sort((a, b) => a.index - b.index)
    }
    firstInput(): InputNode {
        let first = this.sortedChildren()[0]
        if(first == undefined) {
            throw 'cannot call firstInput if Node has no children'
        }
        if(first.hasChildren()) {
            return first.firstInput()
        }
        if(first.hasElem()) {
            return first
        }
        return undefined
    }
    lastInput(): InputNode {
        let last = this.sortedChildren()[Object.keys(this.children).length -1]
        if(last == undefined) {
            throw 'cannot call lastInput if Node has no children'
        }
        if(last.hasChildren()) {
            return last.lastInput()
        }
        if(last.hasElem()) {
            return last
        }
        return undefined
    }

}

const root = new InputNode(0, undefined)


export function registerInput(inputId: number[], inputElem: HTMLElement) {
    let tree = root
    for (let id of inputId) {
        if (!tree.children[id]) {
            tree.children[id] = new InputNode(id, tree)
        }
        tree = tree.children[id]
    }
    tree.inputElem = inputElem
}

export function getTree() {
    return root
}

export function getInput(inputId: number[]) {
    let tree = root
    for (let id of inputId) {
        if (!tree.children[id]) {
            return
        }
        tree = tree.children[id]
    }
    return tree
}

export function nextInput(inputId: number[]) {
    if(inputId == undefined) {
        return
    }
    let next = getInput(inputId)
    if(next == undefined) {
        throw 'This Error should not happen, why is the input no registered ?? Ask devs, unhappy devs'
    }
    next = next.nextInput()
    if(next) {
        next.inputElem.click()
    }

}

export function prevInput(inputId: number[]) {
    if(inputId == undefined) {
        return
    }
    let next = getInput(inputId)
    if(next == undefined) {
        throw 'This Error should not happen, why is the input no registered ?? Ask devs, unhappy devs'
    }
    next = next.prevInput()
    if(next) {
        next.inputElem.click()
    }

}

registerInput([0,0], '0.0' as any)
registerInput([0,1], '0.1' as any)
registerInput([0,2], '0.2' as any)
registerInput([0,3], '0.3' as any)
registerInput([1,0], '1.0' as any)
registerInput([1,2], '1.2' as any)
registerInput([1,3], '1.3' as any)

