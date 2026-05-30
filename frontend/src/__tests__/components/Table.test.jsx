import { render, screen, fireEvent } from '../../test-utils'
import Table, { createColumnHelper } from '../../../components/ui/Table'

const col = createColumnHelper()

const sampleColumns = [
  col.accessor('name', { header: 'Name' }),
  col.accessor('age', { header: 'Age' }),
  col.accessor('email', { header: 'Email' }),
]

const sampleData = [
  { name: 'Alice', age: 22, email: 'alice@example.com' },
  { name: 'Bob', age: 25, email: 'bob@example.com' },
]

describe('Table', () => {
  it('renders column headers', () => {
    render(<Table columns={sampleColumns} data={sampleData} />)
    expect(screen.getByText('Name')).toBeInTheDocument()
    expect(screen.getByText('Age')).toBeInTheDocument()
    expect(screen.getByText('Email')).toBeInTheDocument()
  })

  it('renders row data', () => {
    render(<Table columns={sampleColumns} data={sampleData} />)
    expect(screen.getByText('Alice')).toBeInTheDocument()
    expect(screen.getByText('Bob')).toBeInTheDocument()
    expect(screen.getByText('alice@example.com')).toBeInTheDocument()
    expect(screen.getByText('bob@example.com')).toBeInTheDocument()
  })

  it('shows skeleton rows when isLoading', () => {
    render(<Table columns={sampleColumns} data={[]} isLoading />)
    const skeletons = document.querySelectorAll('.animate-pulse')
    expect(skeletons.length).toBeGreaterThan(0)
  })

  it('shows empty state when data is empty', () => {
    render(<Table columns={sampleColumns} data={[]} />)
    expect(screen.getByText('No results found')).toBeInTheDocument()
  })

  it('renders custom emptyMessage', () => {
    render(
      <Table columns={sampleColumns} data={[]} emptyMessage="Nothing to show here" />
    )
    expect(screen.getByText('Nothing to show here')).toBeInTheDocument()
  })

  it('shows pagination controls when pagination prop provided', () => {
    const pagination = {
      page: 2,
      per_page: 10,
      total: 30,
      pages: 3,
      onPageChange: vi.fn(),
    }
    render(<Table columns={sampleColumns} data={sampleData} pagination={pagination} />)
    expect(screen.getByText('Prev')).toBeInTheDocument()
    expect(screen.getByText('Next')).toBeInTheDocument()
  })

  it('Prev button disabled on first page', () => {
    const pagination = {
      page: 1,
      per_page: 10,
      total: 30,
      pages: 3,
      onPageChange: vi.fn(),
    }
    render(<Table columns={sampleColumns} data={sampleData} pagination={pagination} />)
    const prevBtn = screen.getByText('Prev')
    expect(prevBtn).toBeDisabled()
  })

  it('Next button disabled on last page', () => {
    const pagination = {
      page: 3,
      per_page: 10,
      total: 30,
      pages: 3,
      onPageChange: vi.fn(),
    }
    render(<Table columns={sampleColumns} data={sampleData} pagination={pagination} />)
    const nextBtn = screen.getByText('Next')
    expect(nextBtn).toBeDisabled()
  })

  it('calls onPageChange when Next clicked', () => {
    const onPageChange = vi.fn()
    const pagination = {
      page: 1,
      per_page: 10,
      total: 30,
      pages: 3,
      onPageChange,
    }
    render(<Table columns={sampleColumns} data={sampleData} pagination={pagination} />)
    fireEvent.click(screen.getByText('Next'))
    expect(onPageChange).toHaveBeenCalledWith(2)
  })
})
